"""Linux base service implementation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import contextlib
import errno
import functools
import logging
import os
import select
import socket
import struct
import time

import six

from treadmill import dirwatch
from treadmill import fs
from treadmill import yamlwrapper as yaml
from treadmill.syscall import eventfd

from . import _base_service


_LOGGER = logging.getLogger(__name__)

#: Name of service status file
_STATUS_SOCK = 'status.sock'


class LinuxResourceService(_base_service.ResourceService):
    """Linux server class for all Treadmill services.

    /service_dir/resources/<containerid>-<uid>/ ->
        /apps/<containerid>/rsrc/req-<svc_name>/

    /apps/<container>/rsrc/<svc_name>/
        request.yml
        reply.yml
        svc_req_id

    """

    __slots__ = (
        '_io_eventfd',
    )

    _IO_EVENT_PENDING = struct.pack('@Q', 1)

    def __init__(self, service_dir, impl):
        super(LinuxResourceService, self).__init__(service_dir, impl)
        self._io_eventfd = None

    @property
    def status_sock(self):
        """status socket of the service.
        """
        return os.path.join(self._dir, _STATUS_SOCK)

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
            raise _base_service.ResourceServiceTimeoutError(
                'Service %r timed out' % (self.name),
            )

        return status

    def _run(self, impl, watchdog_lease):
        """Linux implementation of run.
        """
        # Create the status socket
        ss = self._create_status_socket()

        # Run initialization
        impl.initialize(self._dir)

        watcher = dirwatch.DirWatcher(self._rsrc_dir)
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

        loop_timeout = impl.WATCHDOG_HEARTBEAT_SEC // 2
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
            if six.PY2:
                # pylint: disable=W1624,E1136,indexing-exception
                if err[0] != errno.EINTR:
                    raise
            else:
                if err.errno != errno.EINTR:
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
            if isinstance(filedescriptor, int):
                # Already a fd number. Use that.
                fd = filedescriptor
            else:
                fd = filedescriptor.fileno()
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
        for fd in list(poll_callbacks.keys()):
            if fd not in all_fds:
                _LOGGER.debug('Unregistered %r: %r', fd, poll_callbacks[fd])
                poll.unregister(fd)
                del poll_callbacks[fd]

    def clt_update_request(self, req_id):
        """Update an existing request.

        This should only be called by the client instance.
        """
        _update_request(self._rsrc_dir, req_id)

    def _create_status_socket(self):
        """Create a listening socket to process status requests.
        """
        fs.rm_safe(self.status_sock)
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
        if io_res and io_res[-1][0] == dirwatch.DirWatcherEvent.MORE_PENDING:
            _LOGGER.debug('More requests events pending')
            os.write(self._io_eventfd, self._IO_EVENT_PENDING)

        return any(
            [
                callback_res
                for (_, _, callback_res) in
                io_res
            ]
        )


class LinuxBaseResourceServiceImpl(_base_service.BaseResourceServiceImpl):
    """Base interface of Resource Service implementations.
    """

    __slots__ = ()

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

    def retry_request(self, rsrc_id):
        """Force re-evaluation of a request.
        """
        _update_request(self._service_rsrc_dir, rsrc_id)


def _update_request(rsrc_dir, req_id):
    """Update an existing request.

    This should only be called by the client instance.
    """
    svc_req_lnk = os.path.join(rsrc_dir, req_id)
    _LOGGER.debug('Updating %r: %r', req_id, svc_req_lnk)
    # Remove any reply if it exists
    fs.rm_safe(os.path.join(svc_req_lnk, _base_service.REP_FILE))

    # NOTE: This does the equivalent of a touch on the symlink
    try:
        os.lchown(
            svc_req_lnk,
            os.getuid(),
            os.getgid()
        )
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
