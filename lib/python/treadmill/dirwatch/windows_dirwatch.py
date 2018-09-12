"""Implements directory watcher using ReadDirectoryChangesW.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import logging
import os

# E0401: Unable to import windows only pakages
import winerror  # pylint: disable=E0401

import pywintypes  # pylint: disable=E0401
import win32con  # pylint: disable=E0401
import win32event  # pylint: disable=E0401
import win32file  # pylint: disable=E0401

from . import dirwatch_base

_BUFFER_SIZE = 32768
_INVALID_HANDLE_VALUE = -1
_FILE_LIST_DIRECTORY = 0x0001

_ACTION_NAMES = {1: 'CREATE',
                 2: 'DELETE',
                 3: 'MODIFY',
                 4: 'MOVEFROM',
                 5: 'MOVETO'}

_EVENTS = {'CREATE': dirwatch_base.DirWatcherEvent.CREATED,
           'DELETE': dirwatch_base.DirWatcherEvent.DELETED,
           'MODIFY': dirwatch_base.DirWatcherEvent.MODIFIED,
           'MOVEFROM': dirwatch_base.DirWatcherEvent.DELETED,
           'MOVETO': dirwatch_base.DirWatcherEvent.CREATED}

_LOGGER = logging.getLogger(__name__)


class WindowsDirInfo:
    """Windows directory watcher info."""
    __slots__ = (
        'id',
        'path',
        'overlapped',
        'buffer',
        'file'
    )

    def __init__(self, path):
        self.path = path
        self.overlapped = pywintypes.OVERLAPPED()
        self.overlapped.hEvent = win32event.CreateEvent(None, 1, 0, None)
        self.buffer = win32file.AllocateReadBuffer(_BUFFER_SIZE)
        self.file = win32file.CreateFile(
            self.path,
            _FILE_LIST_DIRECTORY,
            (
                win32con.FILE_SHARE_READ |
                win32con.FILE_SHARE_WRITE |
                win32con.FILE_SHARE_DELETE
            ),
            None,
            win32con.OPEN_EXISTING,
            (
                win32con.FILE_FLAG_BACKUP_SEMANTICS |
                win32con.FILE_FLAG_OVERLAPPED
            ),
            None
        )
        self.id = self.overlapped.hEvent.handle

    def close(self):
        """Closes the directory info."""
        self.file.close()
        self.overlapped.hEvent.close()


class WindowsDirWatcher(dirwatch_base.DirWatcher):
    """Windows directory watcher implementation."""
    __slots__ = (
        '_dir_infos',
        '_changed'
    )

    def __init__(self, watch_dir=None):
        self._dir_infos = {}
        self._changed = collections.deque()
        super(WindowsDirWatcher, self).__init__(watch_dir)

    @staticmethod
    def _read_dir(info):
        """Reads the directory for changes async.
        """
        try:
            win32file.ReadDirectoryChangesW(
                info.file,
                info.buffer,
                False,
                (
                    win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                    win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                    win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                    win32con.FILE_NOTIFY_CHANGE_SIZE |
                    win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                    win32con.FILE_NOTIFY_CHANGE_SECURITY
                ),
                info.overlapped
            )
            return True
        except pywintypes.error as exc:
            _LOGGER.warning('Failed to read directory \'%s\': %s',
                            info.path, exc)
            return False

    def _add_dir(self, watch_dir):
        """Add `directory` to the list of watched directories.

        :param watch_dir: watch directory real path
        :returns: watch id
        """
        info = WindowsDirInfo(watch_dir)
        if info.file == _INVALID_HANDLE_VALUE or not self._read_dir(info):
            info.close()
            raise OSError(errno.ENOENT, 'No such file or directory',
                          watch_dir)

        self._dir_infos[info.id] = info
        return info.id

    def _remove_dir(self, watch_id):
        """Remove `directory` from the list of watched directories.

        :param watch_id: watch id
        """
        info = self._dir_infos.get(watch_id)
        if info is not None:
            info.close()
            del self._dir_infos[watch_id]

    def _wait_for_events(self, timeout):
        """Wait for directory change event for up to ``timeout`` seconds.

        :param timeout:
            Time in milliseconds to wait for an event (-1 means forever)
        :returns:
            ``True`` if events were received, ``False`` otherwise.
        """
        ids = [k for k in self._dir_infos]
        rc = win32event.WaitForMultipleObjects(ids, 0, timeout)
        if rc == win32event.WAIT_TIMEOUT:
            return False
        elif rc == win32event.WAIT_FAILED:
            _LOGGER.error('Wait on %r failed', ids)
            return False

        idx = rc - win32event.WAIT_OBJECT_0
        info = self._dir_infos.get(ids[idx])

        if info is not None:
            self._changed.append(info)
            return True

        return False

    def _preempt_watch(self, info, result):
        """Deletes the watch preemptively.
        """
        result.append((dirwatch_base.DirWatcherEvent.DELETED, info.path))
        info.close()
        del self._dir_infos[info.id]

    def _read_events(self):
        """Reads the events from the system and formats as ``DirWatcherEvent``.

        :returns: List of ``(DirWatcherEvent, <path>)``
        """
        result = []

        while self._changed:
            info = self._changed.popleft()

            try:
                size = win32file.GetOverlappedResult(info.file,
                                                     info.overlapped,
                                                     False)
            except win32file.error as exc:
                win32event.ResetEvent(info.overlapped.hEvent)
                _LOGGER.warning(
                    'Failed to get directory changes for \'%s\': %s',
                    info.path, exc)

                if exc.winerror == winerror.ERROR_ACCESS_DENIED:
                    self._preempt_watch(info, result)
                continue

            notifications = win32file.FILE_NOTIFY_INFORMATION(info.buffer,
                                                              size)

            for action, path in notifications:
                action_name = _ACTION_NAMES.get(action)
                path = os.path.join(info.path, path)
                if action_name is None:
                    _LOGGER.error('Received unknown action (%s, \'%s\')',
                                  action, path)
                    continue

                _LOGGER.debug('Received event (%s, \'%s\')', action_name, path)

                event = _EVENTS.get(action_name)
                if event is not None:
                    result.append((event, path))

            win32event.ResetEvent(info.overlapped.hEvent)
            if not self._read_dir(info):
                self._preempt_watch(info, result)

        return result
