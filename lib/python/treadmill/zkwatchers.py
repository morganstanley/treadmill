"""Higher level custom specialized ZK watching API's.

Based on kazoo.recipe.watchers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging

import kazoo.retry
import kazoo.exceptions
from kazoo.protocol import states


_LOGGER = logging.getLogger(__name__)


def _ignore_closed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        """Ignore ConnectionClosedError"""
        try:
            return func(*args, **kwargs)
        except kazoo.exceptions.ConnectionClosedError:
            pass
    return wrapper


class ExistingDataWatch:
    """Watches an existing node for data updates and calls the specified
    function each time it changes.

    The function will also be called the very first time it's
    registered to get the data.

    Supplied function will be passed three arguments: data, stat and event.
    For reconnection or the first call event will be None. If node does not
    exist or is deleted, data and stat will be None and watch will be stopped.
    """
    def __init__(self, client, path, func=None):
        """Create a data watcher for an existing path"""
        self._client = client
        self._path = path
        self._func = func
        self._stopped = False
        self._run_lock = client.handler.lock_object()
        self._version = None
        self._retry = kazoo.retry.KazooRetry(
            max_tries=None, sleep_func=client.handler.sleep_func
        )
        self._used = False

        # Register our session listener if we're going to resume
        # across session losses
        if func is not None:
            self._used = True
            self._client.add_listener(self._session_watcher)
            self._get_data()

    def __call__(self, func):
        """Callable version for use as a decorator"""
        if self._used:
            raise kazoo.exceptions.KazooException(
                'A function has already been associated with this '
                'ExistingDataWatch instance.')

        self._func = func

        self._used = True
        self._client.add_listener(self._session_watcher)
        self._get_data()
        return func

    def _log_func_exception(self, data, stat, event=None):
        try:
            self._func(data, stat, event)
        except Exception as exc:
            _LOGGER.exception(exc)
            raise

    def _stop(self, reason):
        self._stopped = True
        self._client.remove_listener(self._session_watcher)
        _LOGGER.info('Stopping watch on %s: %s', self._path, reason)
        self._func = None

    @_ignore_closed
    def _get_data(self, event=None):
        # Ensure this runs one at a time, possible because the session
        # watcher may trigger a run
        with self._run_lock:
            if self._stopped:
                return

            if event is not None and event.type == 'DELETED':
                self._log_func_exception(None, None, event)
                self._stop('Node deleted')
                return

            try:
                data, stat = self._retry(self._client.get,
                                         self._path, self._watcher)
            except kazoo.exceptions.NoNodeError:
                self._log_func_exception(None, None, event)
                self._stop('Node does not exist')
                return

            if self._version is None:
                _LOGGER.debug('Created watch on %s', self._path)
            else:
                _LOGGER.debug('Renewed watch on %s', self._path)

            # Call our function if its the first time ever, or if the
            # version has changed
            if stat.mzxid != self._version:
                self._version = stat.mzxid
                self._log_func_exception(data, stat, event)

    def _watcher(self, event):
        self._get_data(event=event)

    def _session_watcher(self, state):
        if state == states.KazooState.CONNECTED:
            self._client.handler.spawn(self._get_data)
