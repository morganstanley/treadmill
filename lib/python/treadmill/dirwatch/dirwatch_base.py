"""An interface for a directory watcher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import collections
import logging
import os
import sys

import enum

import six

_LOGGER = logging.getLogger(__name__)


class DirWatcherEvent(enum.Enum):
    """DirWatcher's emitted event types.
    """
    # W0232: Class has no __init__ method
    # pylint: disable=W0232
    CREATED = 'created'
    DELETED = 'deleted'
    MODIFIED = 'modified'
    #: Fake event returned when more events where received than allowed to
    #: process in ``process_events``
    MORE_PENDING = 'more events pending'


# TODO: new pylint circular complains about useless None return and then about
#       assigning from function that does not return.
#
#       Disabling these for now, code need to be refactored to better reflect
#       return types.
#
# pylint: disable=E1111
# [ylint: disable=R1711

@six.add_metaclass(abc.ABCMeta)
class DirWatcher:
    """Directory watcher base, invoking callbacks on file create/delete events.
    """
    __slots__ = (
        'event_list',
        'on_created',
        'on_deleted',
        'on_modified',
        '_watches'
    )

    def __init__(self, watch_dir=None):
        self.event_list = collections.deque()
        self.on_created = self._noop
        self.on_deleted = self._noop
        self.on_modified = self._noop
        self._watches = {}

        if watch_dir is not None:
            self.add_dir(watch_dir)

    @abc.abstractmethod
    def _add_dir(self, watch_dir):
        """Add `directory` to the list of watched directories.

        :param watch_dir: watch directory real path
        :returns: watch id
        """
        raise AssertionError('Abstract method.')

    def add_dir(self, directory):
        """Add `directory` to the list of watched directories.
        """
        watch_dir = os.path.realpath(directory)

        wid = self._add_dir(watch_dir)
        _LOGGER.info('Watching directory %r (id: %r)', watch_dir, wid)
        self._watches[wid] = watch_dir

    @abc.abstractmethod
    def _remove_dir(self, watch_id):
        """Remove `directory` from the list of watched directories.

        :param watch_id: watch id
        """
        raise AssertionError('Abstract method.')

    def remove_dir(self, directory):
        """Remove `directory` from the list of watched directories.
        """
        watch_dir = os.path.realpath(directory)
        for wid, w_dir in self._watches.items():
            if w_dir == watch_dir:
                break
        else:
            wid = None
            _LOGGER.warning('Directory %r not currently watched', watch_dir)
            return

        _LOGGER.info('Unwatching directory %r (id: %r)', watch_dir, wid)
        del self._watches[wid]
        self._remove_dir(wid)

    @staticmethod
    def _noop(event_src):
        """Default NOOP callback"""
        _LOGGER.debug('event on %r', event_src)

    @abc.abstractmethod
    def _wait_for_events(self, timeout):
        """Wait for directory change event for up to ``timeout`` seconds.

        :param timeout:
            Time in seconds to wait for an event (-1 means forever)
        :returns:
            ``True`` if events were received, ``False`` otherwise.
        """
        raise AssertionError('Abstract method.')

    def wait_for_events(self, timeout=-1):
        """Wait for directory change event for up to ``timeout`` seconds.

        :param timeout:
            Time in seconds to wait for an event (-1 means forever)
        :returns:
            ``True`` if events were received, ``False`` otherwise.
        """
        # We already have cached events
        if self.event_list:
            return True

        if timeout != -1:
            timeout *= 1000  # timeout is in milliseconds

        return self._wait_for_events(timeout)

    @abc.abstractmethod
    def _read_events(self):
        """Reads the events from the system and formats as ``DirWatcherEvent``.

        :returns: List of ``(DirWatcherEvent, <path>)``
        """
        raise AssertionError('Abstract method.')

    def process_events(self, max_events=0, resume=False):
        """Process events received.

        This function will parse all received events and invoke the registered
        callbacks accordingly.

        :param ``int`` max_events:
            Maximum number of events to process
        :param ``bool`` resume:
            Continue processing any event that was still in the queue (do not
            read new ones).
        :returns ``list``:
            List of ``(DirWatcherEvent, <path>, <callback_return>)``.
        """
        if max_events <= 0:
            max_events = sys.maxsize

        # If we are out of cached events, get more from inotify
        if not self.event_list and not resume:
            self.event_list.extend(self._read_events())

        results = []
        step = 0
        while self.event_list:
            if step >= max_events:
                # We reach the max number of events we could process
                results.append(
                    (
                        DirWatcherEvent.MORE_PENDING,
                        None,
                        None,
                    )
                )
                break

            step += 1
            event, src_path = self.event_list.popleft()
            res = None

            # E1128: Assigning to function call which only returns None
            if event == DirWatcherEvent.MODIFIED:
                res = self.on_modified(src_path)  # pylint: disable=E1128

            elif event == DirWatcherEvent.DELETED:
                res = self.on_deleted(src_path)  # pylint: disable=E1128

            elif event == DirWatcherEvent.CREATED:
                res = self.on_created(src_path)  # pylint: disable=E1128

            else:
                continue

            results.append(
                (
                    event,
                    src_path,
                    res
                )
            )

        return results
