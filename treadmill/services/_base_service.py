"""Base for all node resource services."""


import abc
import collections
import contextlib
import errno
import functools
import glob
import importlib
import logging
import os
import select
import shutil
import socket
import struct
import tempfile
import time

import yaml

from .. import exc
from .. import fs
from .. import logcontext as lc
from .. import idirwatch
from .. import utils
from .. import watchdog

from ..syscall import eventfd


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

#: Name of the directory holding the resources requests
_RSRC_DIR = 'resources'
#: Name of request payload file
_REQ_FILE = 'request.yml'
#: Name of reply payload file
_REP_FILE = 'reply.yml'
#: Name of service status file
_STATUS_SOCK = 'status.sock'


def _wait_for_file(filename, timeout=60 * 60):
    """Wait at least ``timeout`` seconds for a file to appear or be modified.

    :param ``int`` timeout:
        Minimum amount of seconds to wait for the file.
    :returns ``bool``:
        ``True`` if there was an event, ``False`` otherwise (timeout).
    """
    if timeout is None:
        timeout = 60 * 60

    elif timeout == 0:
        return os.path.exists(filename)

    filedir = os.path.dirname(filename)
    # TODO: Fine tune the watcher mask for efficiency.
    watcher = idirwatch.DirWatcher(filedir)

    now = time.time()
    end_time = now + timeout
    while not os.path.exists(filename):
        if watcher.wait_for_events(timeout=max(0, end_time - now)):
            watcher.process_events()

        now = time.time()
        if now > end_time:
            return False

    return True


class ResourceServiceError(exc.TreadmillError):
    """Base Resource Service error.
    """
    __slots__ = ()

    def __init__(self, message):
        super(ResourceServiceError, self).__init__(message)


class ResourceServiceRequestError(ResourceServiceError):
    """Resource Service Request error.
    """
    __slots__ = ('request')

    def __init__(self, message, request):
        super(ResourceServiceRequestError, self).__init__(message)
        self.request = request


class ResourceServiceTimeoutError(ResourceServiceError, socket.timeout):
    """Resource Service timeout.
    """
    __slots__ = ()

    def __init__(self, message):
        super(ResourceServiceTimeoutError, self).__init__(message)


class ResourceServiceClient(object):
    """Client class for all Treadmill services.

    /apps/<container>/rsrc/req-<svc_name>/
        request.yml
        reply.yml
        svc_req_id
    """

    _REQ_UID_FILE = 'svc_req_id'

    __slots__ = (
        '_serviceinst',
        '_clientdir',
    )

    def __init__(self, serviceinst, clientdir):
        self._serviceinst = serviceinst
        fs.mkdir_safe(clientdir)
        self._clientdir = os.path.realpath(clientdir)

    def create(self, rsrc_id, rsrc_data):
        """Request creation of a resource.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        :param `str` rsrc_data:
            Parameters for the requested resource.
        """
        req_dir = self._req_dirname(rsrc_id)
        os.mkdir(req_dir)  # Will fail if request already exists

        with open(os.path.join(req_dir, _REQ_FILE), 'w') as f:
            os.fchmod(f.fileno(), 0o644)
            yaml.dump(rsrc_data,
                      explicit_start=True, explicit_end=True,
                      default_flow_style=False,
                      stream=f)

        with lc.LogContext(_LOGGER, rsrc_id):
            try:
                svc_req_uuid = self._serviceinst.clt_new_request(rsrc_id,
                                                                 req_dir)

            except OSError as _err:
                # Error registration failed, delete the request.
                _LOGGER.exception('Unable to submit request')
                shutil.rmtree(req_dir)

            with open(os.path.join(req_dir, self._REQ_UID_FILE), 'w') as f:
                os.fchmod(f.fileno(), 0o644)
                f.write(svc_req_uuid)

    def update(self, rsrc_id, rsrc_data):
        """Update an existing resource.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        :param `str` rsrc_data:
            New paramters for the requested resource.
        """
        req_dir = self._req_dirname(rsrc_id)
        with open(os.path.join(req_dir, self._REQ_UID_FILE)) as f:
            os.fchmod(f.fileno(), 0o644)
            svc_req_uuid = f.read().strip()

        with open(os.path.join(req_dir, _REQ_FILE), 'w') as f:
            os.fchmod(f.fileno(), 0o644)
            yaml.dump(rsrc_data,
                      explicit_start=True, explicit_end=True,
                      default_flow_style=False,
                      stream=f)

        with lc.LogContext(_LOGGER, rsrc_id):
            self._serviceinst.clt_update_request(svc_req_uuid)

    def delete(self, rsrc_id):
        """Delete an existing resource.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        """
        with lc.LogContext(_LOGGER, rsrc_id) as log:
            req_dir = self._req_dirname(rsrc_id)
            try:
                with open(os.path.join(req_dir, self._REQ_UID_FILE)) as f:
                    svc_req_uuid = f.read().strip()
            except IOError as err:
                if err.errno == errno.ENOENT:
                    log.warning('Resource %r does not exist', rsrc_id)
                    return
                raise
            self._serviceinst.clt_del_request(svc_req_uuid)
            os.rename(
                req_dir,
                self._bck_dirname(svc_req_uuid)
            )

    def get(self, rsrc_id):
        """Get the result of a resource request.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        :raises ``ResourceServiceRequestError``:
            If the request resulted in error.
        """
        try:
            res = self.wait(rsrc_id, timeout=0)
        except ResourceServiceTimeoutError:
            res = None
        return res

    def wait(self, rsrc_id, timeout=None):
        """Wait for a requested resource to be ready.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        :raises ``ResourceServiceRequestError``:
            If the request resulted in error.
        :raises ``ResourceServiceTimeoutError``:
            If the request was not available before timeout.
        """
        req_dir = self._req_dirname(rsrc_id)
        rep_file = os.path.join(req_dir, _REP_FILE)

        if not _wait_for_file(rep_file, timeout):
            raise ResourceServiceTimeoutError(
                'Resource %r not available in time' % rsrc_id
            )

        try:
            with open(rep_file) as f:
                reply = yaml.load(stream=f)

        except (IOError, OSError) as err:
            if err.errno == errno.ENOENT:
                raise ResourceServiceTimeoutError(
                    'Resource %r not available in time' % rsrc_id
                )

        if isinstance(reply, dict) and '_error' in reply:
            raise ResourceServiceRequestError(reply['_error']['why'],
                                              reply['_error']['input'])

        return reply

    def status(self, timeout=30):
        """Query the status of the resource service.
        """
        return self._serviceinst.status(timeout=timeout)

    def _req_dirname(self, rsrc_id):
        """Request directory name for a given resource id.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        """
        req_dir_name = 'req-{name}-{rsrc_id}'.format(
            name=self._serviceinst.name,
            rsrc_id=rsrc_id
        )
        req_dir = os.path.join(self._clientdir, req_dir_name)
        return req_dir

    def _bck_dirname(self, req_uuid):
        """Return a unique backup directory name.
        """
        bck_dir_name = 'bck{ts}-{name}-{req_uuid}'.format(
            name=self._serviceinst.name,
            req_uuid=req_uuid,
            ts=int(time.time()),
        )
        bck_dir = os.path.join(self._clientdir, bck_dir_name)
        return bck_dir


class ResourceService(object):
    """Server class for all Treadmill services.

    /service_dir/resources/<containerid>-<uid>/ ->
        /apps/<containerid>/rsrc/req-<svc_name>/

    /apps/<container>/rsrc/<svc_name>/
        request.yml
        reply.yml
        svc_req_id

    """

    __slots__ = (
        '_is_dead',
        '_dir',
        '_rsrc_dir',
        '_service_impl',
        '_service_class',
        '_service_name',
        '_io_eventfd',
    )

    _IO_EVENT_PENDING = struct.pack('@Q', 1)

    def __init__(self, service_dir, impl):
        fs.mkdir_safe(service_dir)
        self._dir = os.path.realpath(service_dir)
        self._rsrc_dir = os.path.join(self._dir, _RSRC_DIR)
        fs.mkdir_safe(self._rsrc_dir)
        self._is_dead = False
        self._service_impl = impl
        self._service_class = None
        self._io_eventfd = None
        # Figure out the service's name
        if isinstance(self._service_impl, str):
            svc_name = self._service_impl.rsplit('.', 1)[-1]
        else:
            svc_name = self._service_impl.__name__
        self._service_name = svc_name

    @property
    def name(self):
        """Name of the service."""
        return self._service_name

    @property
    def status_sock(self):
        """status socket of the service.
        """
        return os.path.join(self._dir, _STATUS_SOCK)

    def make_client(self, client_dir):
        """Create a client using `clientdir` as request dir location.
        """
        return ResourceServiceClient(self, client_dir)

    def status(self, timeout=30):
        """Query the status of the resource service.

        :param ``float`` timeout:
            Wait at least timeout seconds for the service to reply.
        :raises ``ResourceServiceTimeoutError``:
            If the requested service does not come up before timeout.
        :raises ``socket.error``:
            If there is a communication error with the service.
        """
        backoff = 0
        while backoff <= (timeout / 2):
            with contextlib.closing(socket.socket(socket.AF_UNIX,
                                                  type=socket.SOCK_STREAM,
                                                  proto=0)) as status_socket:
                try:
                    status_socket.connect(self.status_sock)
                    status = yaml.load(stream=status_socket.makefile('r'))
                except socket.error as err:
                    if err.errno in (errno.ECONNREFUSED, errno.ENOENT):
                        status = None
                    else:
                        raise

            if status is not None:
                break

            _LOGGER.info('Waiting for service %r to become available',
                         self.name)
            # Implement a backoff mechanism
            backoff += (backoff or 1)
            time.sleep(backoff)

        else:
            raise ResourceServiceTimeoutError(
                'Service %r timed out' % (self.name),
            )

        return status

    def get(self, req_id):
        """Read the reply of a given request.
        """
        rep_file = os.path.join(self._rsrc_dir, req_id, _REP_FILE)
        with open(rep_file) as f:
            reply = yaml.load(stream=f)

        if isinstance(reply, dict) and '_error' in reply:
            raise ResourceServiceRequestError(reply['_error']['why'],
                                              reply['_error']['input'])

        return reply

    def run(self, watchdogs_dir, *impl_args, **impl_kwargs):
        """Run the service."""
        # Load the implementation
        if self._service_class is None:
            self._service_class = self._load_impl()
        impl = self._service_class(*impl_args, **impl_kwargs)

        # Setup the watchdog
        watchdogs = watchdog.Watchdog(os.path.realpath(watchdogs_dir))
        watchdog_lease = watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=self.name),
            timeout='{hb:d}s'.format(hb=impl.WATCHDOG_HEARTBEAT_SEC),
            content='Service %r failed' % self.name
        )

        # Create the status socket
        ss = self._create_status_socket()

        # Run initialization
        impl.initialize(self._dir)

        watcher = idirwatch.DirWatcher(self._rsrc_dir)
        # Call all the callbacks with the implementation instance
        watcher.on_created = functools.partial(self._on_created, impl)
        watcher.on_deleted = functools.partial(self._on_deleted, impl)
        # NOTE: A modified request is treated as a brand new request
        watcher.on_modified = functools.partial(self._on_created, impl)
        self._io_eventfd = eventfd.eventfd(0, eventfd.EFD_CLOEXEC)

        # Before starting, check the request directory
        svcs = self._check_requests()
        # and "fake" a created event on all the existing requests
        for existing_svcs in svcs:
            self._on_created(impl, existing_svcs)

        # Before starting, make sure backend state and service state are
        # synchronized.
        impl.synchronize()

        # Report service status
        status_info = {}
        status_info.update(impl.report_status())

        # Setup the poll object
        loop_poll = select.poll()
        loop_callbacks = {}

        base_event_handlers = [
            (
                self._io_eventfd,
                select.POLLIN,
                functools.partial(
                    self._handle_queued_io_events,
                    watcher=watcher,
                    impl=impl,
                )
            ),
            (
                watcher.inotify,
                select.POLLIN,
                functools.partial(
                    self._handle_io_events,
                    watcher=watcher,
                    impl=impl,
                )
            ),
            (
                ss,
                select.POLLIN,
                functools.partial(
                    self._publish_status,
                    status_socket=ss,
                    status_info=status_info,
                )
            ),
        ]
        # Initial collection of implementation' event handlers
        impl_event_handlers = impl.event_handlers()

        self._update_poll_registration(
            loop_poll,
            loop_callbacks,
            base_event_handlers + impl_event_handlers,
        )

        loop_timeout = impl.WATCHDOG_HEARTBEAT_SEC / 2
        while not self._is_dead:

            # Check for events
            updated = self._run_events(
                loop_poll,
                loop_timeout,
                loop_callbacks,
            )

            if updated:
                # Report service status
                status_info.clear()
                status_info.update(impl.report_status())

                # Update poll registration if needed
                impl_event_handlers = impl.event_handlers()
                self._update_poll_registration(
                    loop_poll, loop_callbacks,
                    base_event_handlers + impl_event_handlers,
                )

            # Clean up stale requests
            self._check_requests()

            # Heartbeat
            watchdog_lease.heartbeat()

        _LOGGER.info('Shuting down %r service', self.name)
        # Remove the service heartbeat
        watchdog_lease.remove()

    def _publish_status(self, status_socket, status_info):
        """Publish service status on the incomming connection on socket
        """
        with contextlib.closing(status_socket.accept()[0]) as clt:
            clt_stream = clt.makefile(mode='w')
            try:
                yaml.dump(status_info,
                          explicit_start=True, explicit_end=True,
                          default_flow_style=False,
                          stream=clt_stream)
                clt_stream.flush()
            except socket.error as err:
                if err.errno == errno.EPIPE:
                    pass
                else:
                    raise

    @staticmethod
    def _run_events(loop_poll, loop_timeout, loop_callbacks):
        """Wait for events up to `loop_timeout` and execute each of the
        registered handlers.

        :returns ``bool``:
            True is any of the callbacks returned True
        """
        pending_callbacks = []

        try:
            # poll timeout is in milliseconds
            for (fd, _event) in loop_poll.poll(loop_timeout * 1000):
                fd_data = loop_callbacks[fd]
                _LOGGER.debug('Event on %r: %r', fd, fd_data)
                pending_callbacks.append(
                    fd_data['callback']
                )

        except select.error as err:
            # Ignore signal interruptions
            if err[0] != errno.EINTR:
                raise

        results = [
            callback()
            for callback in pending_callbacks
        ]

        return any(results)

    @staticmethod
    def _update_poll_registration(poll, poll_callbacks, handlers):
        """Setup the poll object and callbacks based on handlers.
        """
        def _normalize_fd(filedescriptor):
            """Return the fd number or filedescriptor.
            """
            if not isinstance(filedescriptor, int):
                fd = filedescriptor.fileno()
            else:
                fd = filedescriptor
            return fd

        handlers = [
            (_normalize_fd(fd), events, callback)
            for (fd, events, callback) in handlers
        ]

        for (fd, events, callback) in handlers:
            fd_data = {'callback': callback, 'events': events}
            if fd not in poll_callbacks:
                poll.register(fd, events)
                poll_callbacks[fd] = fd_data
                _LOGGER.debug('Registered %r: %r', fd, fd_data)

            elif poll_callbacks[fd] != fd_data:
                poll.modify(fd, events)
                poll_callbacks[fd] = fd_data
                _LOGGER.debug('Updated %r: %r', fd, fd_data)

        all_fds = set(handler[0] for handler in handlers)
        for fd in poll_callbacks.keys():
            if fd not in all_fds:
                _LOGGER.debug('Unregistered %r: %r', fd, poll_callbacks[fd])
                poll.unregister(fd)
                del poll_callbacks[fd]

    def _load_impl(self):
        """Load the implementation class of the service.
        """
        if isinstance(self._service_impl, str):
            (module_name, cls_name) = self._service_impl.rsplit('.', 1)
            impl_module = importlib.import_module(module_name)
            impl_class = getattr(impl_module, cls_name)
        else:
            impl_class = self._service_impl

        assert issubclass(impl_class, BaseResourceServiceImpl), \
            'Invalid implementation %r' % impl_class

        return impl_class

    def clt_new_request(self, req_id, req_data_dir):
        """Add a request data dir as `req_id` to the service.

        This should only be called by the client instance.
        """
        svc_req_lnk = os.path.join(self._rsrc_dir, req_id)
        _LOGGER.info('Registering %r: %r -> %r',
                     req_id, svc_req_lnk, req_data_dir)
        # NOTE(boysson): We use a temporary file + rename behavior to override
        #                any potential old symlinks.
        tmpsymlink = tempfile.mktemp(dir=self._rsrc_dir,
                                     prefix='.tmp' + req_id)
        os.symlink(req_data_dir, tmpsymlink)
        os.rename(tmpsymlink, svc_req_lnk)
        return req_id

    def clt_del_request(self, req_id):
        """Remove an existing request.

        This should only be called by the client instance.
        """
        svc_req_lnk = os.path.join(self._rsrc_dir, req_id)
        _LOGGER.info('Unegistering %r: %r', req_id, svc_req_lnk)
        try:
            os.unlink(svc_req_lnk)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

        return req_id

    def clt_update_request(self, req_id):
        """Update an existing request.

        This should only be called by the client instance.
        """
        svc_req_lnk = os.path.join(self._rsrc_dir, req_id)
        _LOGGER.debug('Updating %r: %r',
                      req_id, svc_req_lnk)
        # Remove any reply if it exists
        try:
            os.unlink(os.path.join(svc_req_lnk, _REP_FILE))
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

        # NOTE(boysson): This does the equivalent of a touch on the symlink
        try:
            os.lchown(
                svc_req_lnk,
                os.getuid(),
                os.getgid()
            )
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

    def _check_requests(self):
        """Check each existing request and remove stale ones.
        """
        svcs = collections.deque()
        for svc in glob.glob(os.path.join(self._rsrc_dir, '*')):
            try:
                os.stat(svc)
                svcs.append(svc)

            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning('Deleting stale request: %r', svc)
                    os.unlink(svc)
                else:
                    raise

        return svcs

    def _create_status_socket(self):
        """Create a listening socket to process status requests.
        """
        try:
            os.unlink(self.status_sock)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        status_socket = socket.socket(
            family=socket.AF_UNIX,
            type=socket.SOCK_STREAM,
            proto=0
        )
        status_socket.bind(self.status_sock)
        os.chmod(self.status_sock, 0o666)
        status_socket.listen(5)
        return status_socket

    def _handle_queued_io_events(self, watcher, impl):
        """Process queued IO events.
        Base service IO event handler (dispatches to on_created/on_deleted.

        :returns ``bool``:
            ``True`` if any of the event handlers returns ``True``.
        """
        # Always start by clearing the IO event fd. We will reset it if we need
        # below (there is always 8 bytes in a eventfd).
        os.read(self._io_eventfd, 8)

        return self._handle_io_events(watcher=watcher, impl=impl, resume=True)

    def _handle_io_events(self, watcher, impl, resume=False):
        """Process IO events.
        Base service IO event handler (dispatches to on_created/on_deleted.

        :returns ``bool``:
            ``True`` if any of the event handlers returns ``True``.
        """
        io_res = watcher.process_events(
            max_events=impl.MAX_REQUEST_PER_CYCLE,
            resume=resume
        )

        # Check if there were more events to process
        if io_res and io_res[-1][0] == idirwatch.DirWatcherEvent.MORE_PENDING:
            _LOGGER.debug('More requests events pending')
            os.write(self._io_eventfd, self._IO_EVENT_PENDING)

        return any(
            [
                callback_res
                for (_, _, callback_res) in
                io_res
            ]
        )

    def _on_created(self, impl, filepath):
        """Private handler for request creation events.
        """
        # Avoid triggering on changes to the service directory itself.
        if filepath == self._rsrc_dir:
            return

        req_id = os.path.basename(filepath)

        # Avoid triggerring on temporary files
        if req_id[0] == '.':
            return

        req_file = os.path.join(filepath, _REQ_FILE)
        rep_file = os.path.join(filepath, _REP_FILE)

        try:
            with open(req_file) as f:
                req_data = yaml.load(stream=f)

        except IOError as err:
            if (err.errno == errno.ENOENT or
                    err.errno == errno.ENOTDIR):
                _LOGGER.exception('Removing invalid request: %r', req_id)
                os.unlink(filepath)
                return
            raise

        try:
            # TODO: We should also validate the req_id format
            utils.validate(req_data, impl.PAYLOAD_SCHEMA)
            res = impl.on_create_request(req_id, req_data)

        except exc.InvalidInputError as err:
            _LOGGER.error('Invalid request data: %r: %s', req_data, err)
            res = {'_error': {'input': req_data, 'why': str(err)}}

        except Exception as err:  # pylint: disable=W0703
            _LOGGER.exception('Unable to process request: %r %r:',
                              req_id, req_data)
            res = {'_error': {'input': req_data, 'why': str(err)}}

        if res is None:
            # Request was not actioned
            return False

        _LOGGER.debug('created %r', req_id)

        with tempfile.NamedTemporaryFile(dir=filepath,
                                         delete=False,
                                         mode='w') as f:
            os.fchmod(f.fileno(), 0o644)
            yaml.dump(res,
                      explicit_start=True, explicit_end=True,
                      default_flow_style=False,
                      stream=f)

        os.rename(f.name, rep_file)
        # Return True if there were no error
        return not bool(res.get('_error', False))

    def _on_deleted(self, impl, filepath):
        """Private handler for request deletion events.
        """
        req_id = os.path.basename(filepath)

        # Avoid triggerring on temporary files
        if req_id[0] == '.':
            return

        _LOGGER.debug('deleted %r', req_id)

        # TODO: We should also validate the req_id format
        res = impl.on_delete_request(req_id)

        return res


class BaseResourceServiceImpl(object, metaclass=abc.ABCMeta):
    """Base interface of Resource Service implementations.
    """
    __slots__ = (
        '_service_dir',
        '_service_rsrc_dir',
    )

    MAX_REQUEST_PER_CYCLE = 5
    PAYLOAD_SCHEMA = ()
    WATCHDOG_HEARTBEAT_SEC = 60

    def __init__(self):
        self._service_dir = None
        self._service_rsrc_dir = None

    @abc.abstractmethod
    def initialize(self, service_dir):
        """Service initialization."""
        self._service_dir = service_dir
        self._service_rsrc_dir = os.path.join(service_dir, _RSRC_DIR)

    @abc.abstractmethod
    def synchronize(self):
        """Assert that the internal state of the service matches the backend
        state.
        """
        return

    @abc.abstractmethod
    def report_status(self):
        """Record service status information.

        Will be called at least once after initialization is complete.
        """
        return {}

    def event_handlers(self):
        """Returns a list of `(fileno, event, callback)` to be registered in
        the event loop.
        """
        return []

    @abc.abstractmethod
    def on_create_request(self, rsrc_id, rsrc_data):
        """Call back invoked when a new resource request is received.

        Args:
            rsrc_id ``str``: Unique resource identifier
            rsrc_data ``dict``: Resource request metadata

        Returns:
            ``dict``: Result communicated back to the requestor, ``None``,
            ``False`` or ``{}`` if no changes to the service were made.
        """
        pass

    @abc.abstractmethod
    def on_delete_request(self, rsrc_id):
        """Call back invoked when a resource is deleted.

        Arguments::
            rsrc_id ``str``: Unique resource identifier
        """
        pass
