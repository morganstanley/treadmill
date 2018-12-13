"""Base for all node resource services.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import collections
import errno
import glob
import io
import logging
import os
import socket
import struct
import tempfile
import time

import six

from treadmill import dirwatch
from treadmill import exc
from treadmill import fs
from treadmill import logcontext as lc
from treadmill import plugin_manager
from treadmill import utils
from treadmill import watchdog
from treadmill import yamlwrapper as yaml


_LOGGER = logging.getLogger(__name__)

#: Name of the directory holding the resources requests
RSRC_DIR = 'resources'
#: Name of request payload file
REQ_FILE = 'request.yml'
#: Name of reply payload file
REP_FILE = 'reply.yml'
#: Default Resource Service timeout
DEFAULT_TIMEOUT = 15 * 60


def wait_for_file(filename, timeout=None):
    """Wait at least ``timeout`` seconds for a file to appear or be modified.

    :param ``int`` timeout:
        Minimum amount of seconds to wait for the file.
    :returns ``bool``:
        ``True`` if there was an event, ``False`` otherwise (timeout).
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    elif timeout == 0:
        return os.path.exists(filename)

    filedir = os.path.dirname(filename)
    # TODO: Fine tune the watcher mask for efficiency.
    watcher = dirwatch.DirWatcher(filedir)

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


class ResourceServiceRequestError(ResourceServiceError):
    """Resource Service Request error.
    """
    __slots__ = (
        'request',
    )

    def __init__(self, message, request):
        super(ResourceServiceRequestError, self).__init__(message)
        self.request = request


class ResourceServiceTimeoutError(ResourceServiceError, socket.timeout):
    """Resource Service timeout.
    """
    __slots__ = ()


class ResourceServiceClient:
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

    def put(self, rsrc_id, rsrc_data):
        """Request creation/update of a resource.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        :param `str` rsrc_data:
            (New) Parameters for the requested resource.
        """
        req_dir = self._req_dirname(rsrc_id)
        fs.mkdir_safe(req_dir)

        with io.open(os.path.join(req_dir, REQ_FILE), 'w') as f:
            if os.name == 'posix':
                os.fchmod(f.fileno(), 0o644)
            yaml.dump(rsrc_data,
                      explicit_start=True, explicit_end=True,
                      default_flow_style=False,
                      stream=f)

        req_uuid_file = os.path.join(req_dir, self._REQ_UID_FILE)
        try:
            with io.open(req_uuid_file) as f:
                svc_req_uuid = f.read().strip()
        except IOError as err:
            if err.errno == errno.ENOENT:
                svc_req_uuid = None
            else:
                raise

        with lc.LogContext(_LOGGER, rsrc_id):
            if svc_req_uuid is None:
                try:
                    # New request
                    svc_req_uuid = self._serviceinst.clt_new_request(rsrc_id,
                                                                     req_dir)
                    # Write down the UUID
                    with io.open(req_uuid_file, 'w') as f:
                        f.write(svc_req_uuid)
                        os.fchmod(f.fileno(), 0o644)

                except OSError:
                    # Error registration failed, delete the request.
                    _LOGGER.exception('Unable to submit request')
                    fs.rmtree_safe(req_dir)

            else:
                self._serviceinst.clt_update_request(svc_req_uuid)

    def delete(self, rsrc_id):
        """Delete an existing resource.

        :param `str` rsrc_id:
            Unique identifier for the requested resource.
        """
        with lc.LogContext(_LOGGER, rsrc_id,
                           adapter_cls=lc.ContainerAdapter) as log:
            req_dir = self._req_dirname(rsrc_id)
            try:
                with io.open(os.path.join(req_dir, self._REQ_UID_FILE)) as f:
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
        rep_file = os.path.join(req_dir, REP_FILE)

        if not wait_for_file(rep_file, timeout):
            raise ResourceServiceTimeoutError(
                'Resource %r not available in time' % rsrc_id
            )

        try:
            with io.open(rep_file) as f:
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


@six.add_metaclass(abc.ABCMeta)
class ResourceService:
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
    )

    _IO_EVENT_PENDING = struct.pack('@Q', 1)

    def __init__(self, service_dir, impl):
        fs.mkdir_safe(service_dir)
        self._dir = os.path.realpath(service_dir)
        self._rsrc_dir = os.path.join(self._dir, RSRC_DIR)
        fs.mkdir_safe(self._rsrc_dir)
        self._is_dead = False
        self._service_impl = impl
        self._service_class = None
        # Figure out the service's name
        if isinstance(self._service_impl, six.string_types):
            svc_name = self._service_impl.rsplit('.', 1)[-1]
        else:
            svc_name = self._service_impl.__name__
        self._service_name = svc_name

    @property
    def name(self):
        """Name of the service."""
        return self._service_name

    def make_client(self, client_dir):
        """Create a client using `clientdir` as request dir location.
        """
        return ResourceServiceClient(self, client_dir)

    @abc.abstractmethod
    def status(self, timeout=30):
        """Query the status of the resource service.

        :param ``float`` timeout:
            Wait at least timeout seconds for the service to reply.
        :raises ``ResourceServiceTimeoutError``:
            If the requested service does not come up before timeout.
        :raises ``socket.error``:
            If there is a communication error with the service.
        """

    def get(self, req_id):
        """Read the reply of a given request.
        """
        rep_file = os.path.join(self._rsrc_dir, req_id, REP_FILE)
        with io.open(rep_file) as f:
            reply = yaml.load(stream=f)

        if isinstance(reply, dict) and '_error' in reply:
            raise ResourceServiceRequestError(reply['_error']['why'],
                                              reply['_error']['input'])

        return reply

    @abc.abstractmethod
    def _run(self, impl, watchdog_lease):
        """Implementation specifc run.
        """

    def run(self, watchdogs_dir, *impl_args, **impl_kwargs):
        """Run the service.

        The run procedure will first initialize the service's implementation,
        the setup the service's watchdog, and start the service resource
        resynchronization procedure.

        This procedure is in 4 phases to handle both fresh starts and restarts.

        $ Call the implementation's :function:`initialize` function which
        allows the implementation to query and import the backend resource's
        state.
        $ Setup the service request watcher.
        $ Import all existing requests (passing them to the
        :function:`on_created` implementation's handler.
        $ Call the implementation's :function:`synchronize` function which
        expunges anything allocated against the backend resource that doesn't
        have a matching request anymore.

        The implementation is expected to implement two handlers:

        * :function:`on_created` that handles new resource requests or update
        to existing resource request (implementation is expected to be
        idem-potent.
        * :function:`on_deleted` that handlers delation of resource requests.
        It should properly handle the case where the backend resource is
        already gone.

        :param ``str`` watchdogs_dir:
            Path to the watchdogs directory.
        :param ``tuple`` impl_args:
            Arguments passed to the implementation's  constructor.
        :param ``dict`` impl_kwargs:
            Keywords arguments passed to the implementation's  constructor.
        """
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

        self._run(impl, watchdog_lease)

        _LOGGER.info('Shuting down %r service', self.name)
        # Remove the service heartbeat
        watchdog_lease.remove()

    def _load_impl(self):
        """Load the implementation class of the service.
        """
        if isinstance(self._service_impl, six.string_types):
            impl_class = plugin_manager.load('treadmill.services',
                                             self._service_impl)
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
        _LOGGER.info('Unregistering %r: %r', req_id, svc_req_lnk)
        fs.rm_safe(svc_req_lnk)

        return req_id

    @abc.abstractmethod
    def clt_update_request(self, req_id):
        """Update an existing request.

        This should only be called by the client instance.
        """

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
                    fs.rm_safe(svc)
                else:
                    raise

        return svcs

    def _on_created(self, impl, filepath):
        """Private handler for request creation events.
        """
        # Avoid triggering on changes to the service directory itself.
        if filepath == self._rsrc_dir:
            return False

        req_id = os.path.basename(filepath)

        # Avoid triggerring on temporary files
        if req_id[0] == '.':
            return False

        req_file = os.path.join(filepath, REQ_FILE)
        rep_file = os.path.join(filepath, REP_FILE)

        try:
            with io.open(req_file) as f:
                req_data = yaml.load(stream=f)

        except IOError as err:
            if (err.errno == errno.ENOENT or
                    err.errno == errno.ENOTDIR):
                _LOGGER.exception('Removing invalid request: %r', req_id)
                try:
                    fs.rm_safe(filepath)
                except OSError as rm_err:
                    if rm_err.errno == errno.EISDIR:
                        fs.rmtree_safe(filepath)
                    else:
                        raise
                return False
            raise

        # TODO: We should also validate the req_id format
        with lc.LogContext(_LOGGER, req_id,
                           adapter_cls=lc.ContainerAdapter) as log:

            log.debug('created %r: %r', req_id, req_data)

            try:
                # TODO: We should also validate the req_id format
                utils.validate(req_data, impl.PAYLOAD_SCHEMA)
                res = impl.on_create_request(req_id, req_data)

            except exc.InvalidInputError as err:
                log.error('Invalid request data: %r: %s', req_data, err)
                res = {'_error': {'input': req_data, 'why': str(err)}}

            except Exception as err:  # pylint: disable=W0703
                log.exception('Unable to process request: %r %r:',
                              req_id, req_data)
                res = {'_error': {'input': req_data, 'why': str(err)}}

        if res is None:
            # Request was not actioned
            return False

        fs.write_safe(
            rep_file,
            lambda f: yaml.dump(
                res, explicit_start=True, explicit_end=True,
                default_flow_style=False, stream=f
            ),
            mode='w',
            permission=0o644
        )

        # Return True if there were no error
        return not bool(res.get('_error', False))

    def _on_deleted(self, impl, filepath):
        """Private handler for request deletion events.
        """
        req_id = os.path.basename(filepath)

        # Avoid triggerring on temporary files
        if req_id[0] == '.':
            return None

        # TODO: We should also validate the req_id format
        with lc.LogContext(_LOGGER, req_id,
                           adapter_cls=lc.ContainerAdapter) as log:

            log.debug('deleted %r', req_id)
            res = impl.on_delete_request(req_id)

        return res


@six.add_metaclass(abc.ABCMeta)
class BaseResourceServiceImpl:
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
        self._service_rsrc_dir = os.path.join(service_dir, RSRC_DIR)

    @abc.abstractmethod
    def synchronize(self):
        """Assert that the internal state of the service matches the backend
        state.
        """

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

    @abc.abstractmethod
    def on_delete_request(self, rsrc_id):
        """Call back invoked when a resource is deleted.

        Arguments::
            rsrc_id ``str``: Unique resource identifier
        """

    @abc.abstractmethod
    def retry_request(self, rsrc_id):
        """Force re-evaluation of a request.

        Arguments::
            rsrc_id ``str``: Unique resource identifier
        """
