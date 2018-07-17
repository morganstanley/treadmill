"""A dispatcher for directory watcher events
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import os

from . import dirwatch_base


class DirWatcherDispatcher:
    """Dispatches directory watcher events to multiple handlers.
    """

    __slots__ = (
        '_dirwatcher',
        '_configs',
    )

    def __init__(self, dirwatcher):
        self._dirwatcher = dirwatcher
        self._configs = []
        self._dirwatcher.on_created = self._on_created
        self._dirwatcher.on_deleted = self._on_deleted
        self._dirwatcher.on_modified = self._on_modified

    @property
    def dirwatcher(self):
        """Gets the dirwatcher which this dispatcher is tied to.
        """
        return self._dirwatcher

    def register(self, path, events):
        """Registers a handler for a list of events at the given path.
        """
        if path is None or not isinstance(events, dict):
            return

        self._configs.append({
            'path': path,
            'events': events
        })
        self._configs.sort(key=lambda x: x['path'], reverse=True)

    def _trigger_handler(self, path, event):
        """Triggers a handler for the given path and event.
        """
        watch_dir = os.path.dirname(path)
        for config in self._configs:
            if not fnmatch.fnmatch(watch_dir, config['path']):
                continue

            events = config['events']
            if event not in events:
                continue

            func = events[event]
            if callable(func):
                func(path)
                return

    def _on_created(self, path):
        """Handles path created events from the directory watcher.
        """
        self._trigger_handler(path, dirwatch_base.DirWatcherEvent.CREATED)

    def _on_deleted(self, path):
        """Handles path deleted events from the directory watcher.
        """
        self._trigger_handler(path, dirwatch_base.DirWatcherEvent.DELETED)

    def _on_modified(self, path):
        """Handles path modified events from the directory watcher.
        """
        self._trigger_handler(path, dirwatch_base.DirWatcherEvent.MODIFIED)
