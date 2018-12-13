"""Windows base service implementation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import functools
import logging
import os

# Disable E0401: unable to import on linux
import win32security  # pylint: disable=E0401

from treadmill import dirwatch
from treadmill import fs

from . import _base_service


_LOGGER = logging.getLogger(__name__)


class WindowsResourceService(_base_service.ResourceService):
    """Windows server class for all Treadmill services.

    /service_dir/resources/<containerid>-<uid>/ ->
        /apps/<containerid>/rsrc/req-<svc_name>/

    /apps/<container>/rsrc/<svc_name>/
        request.yml
        reply.yml
        svc_req_id

    """

    __slots__ = ()

    def status(self, timeout=30):
        """Query the status of the resource service.
        """
        # TODO: implement status for windows

    def _run(self, impl, watchdog_lease):
        """Linux implementation of run.
        """
        # Run initialization
        impl.initialize(self._dir)

        watcher = dirwatch.DirWatcher(self._rsrc_dir)
        # Call all the callbacks with the implementation instance
        watcher.on_created = functools.partial(self._on_created, impl)
        watcher.on_deleted = functools.partial(self._on_deleted, impl)
        # NOTE: A modified request is treated as a brand new request
        watcher.on_modified = functools.partial(self._on_created, impl)

        # Before starting, check the request directory
        svcs = self._check_requests()
        # and "fake" a created event on all the existing requests
        for existing_svcs in svcs:
            self._on_created(impl, existing_svcs)

        # Before starting, make sure backend state and service state are
        # synchronized.
        impl.synchronize()

        loop_timeout = impl.WATCHDOG_HEARTBEAT_SEC // 2
        while not self._is_dead:
            if watcher.wait_for_events(timeout=loop_timeout):
                watcher.process_events()

            # Clean up stale requests
            self._check_requests()

            # Heartbeat
            watchdog_lease.heartbeat()

    def clt_update_request(self, req_id):
        """Update an existing request.

        This should only be called by the client instance.
        """
        _update_request(self._rsrc_dir, req_id)


# Disable W0223: pylint thinks that it is not abstract
# pylint: disable=W0223
class WindowsBaseResourceServiceImpl(_base_service.BaseResourceServiceImpl):
    """Base interface of Resource Service implementations.
    """

    __slots__ = ()

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
        sd = win32security.GetFileSecurity(
            svc_req_lnk,
            win32security.DACL_SECURITY_INFORMATION
        )
        win32security.SetFileSecurity(
            svc_req_lnk,
            win32security.DACL_SECURITY_INFORMATION,
            sd
        )
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
