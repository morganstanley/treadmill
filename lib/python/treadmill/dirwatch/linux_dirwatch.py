"""Implements directory watcher using inofify.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import select

import six

from treadmill.syscall import inotify

from . import dirwatch_base

_LOGGER = logging.getLogger(__name__)


class LinuxDirWatcher(dirwatch_base.DirWatcher):
    """Linux directory watcher implementation."""

    __slots__ = (
        'inotify',
        'poll'
    )

    def __init__(self, watch_dir=None):
        self.inotify = inotify.Inotify(inotify.IN_CLOEXEC)
        self.poll = select.poll()
        self.poll.register(self.inotify, select.POLLIN)
        super(LinuxDirWatcher, self).__init__(watch_dir)

    def _add_dir(self, watch_dir):
        """Add `directory` to the list of watched directories.

        :param watch_dir: watch directory real path
        :returns: watch id
        """
        return self.inotify.add_watch(
            watch_dir,
            event_mask=(
                inotify.IN_ATTRIB |
                inotify.IN_CREATE |
                inotify.IN_DELETE |
                inotify.IN_DELETE_SELF |
                inotify.IN_MODIFY |
                inotify.IN_MOVE
            )
        )

    def _remove_dir(self, watch_id):
        """Remove `directory` from the list of watched directories.

        :param watch_id: watch id
        """
        self.inotify.remove_watch(watch_id)

    def _wait_for_events(self, timeout):
        """Wait for directory change event for up to ``timeout`` seconds.

        :param timeout:
            Time in milliseconds to wait for an event (-1 means forever)
        :returns:
            ``True`` if events were received, ``False`` otherwise.
        """
        try:
            rc = self.poll.poll(timeout)
            return bool(rc)
        except select.error as err:
            if six.PY2:
                # pylint: disable=W1624,E1136,indexing-exception
                if err[0] == errno.EINTR:
                    return False
            else:
                if err.errno == errno.EINTR:
                    return False
            raise

    def _read_events(self):
        """Reads the events from the system and formats as ``DirWatcherEvent``.

        :returns: List of ``(DirWatcherEvent, <path>)``
        """
        results = []
        events = self.inotify.read_events()

        for event in events:
            if (event.is_modify or
                    event.is_attrib):
                results.append(
                    (
                        dirwatch_base.DirWatcherEvent.MODIFIED,
                        event.src_path
                    )
                )

            elif (event.is_delete or
                  event.is_moved_from or
                  event.is_delete_self):
                results.append(
                    (
                        dirwatch_base.DirWatcherEvent.DELETED,
                        event.src_path
                    )
                )

            elif (event.is_create or
                  event.is_moved_to):
                results.append(
                    (
                        dirwatch_base.DirWatcherEvent.CREATED,
                        event.src_path
                    )
                )

            elif event.mask == inotify.IN_IGNORED:
                if self._watches.pop(event.wd, None):
                    _LOGGER.info('Watch on %r auto-removed', event.src_path)

        return results
