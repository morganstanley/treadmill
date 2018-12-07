"""Publish trace events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os

from treadmill import dirwatch
from treadmill import utils

from treadmill.trace.app import zk as app_zk
from treadmill.trace.server import zk as server_zk


_LOGGER = logging.getLogger(__name__)


class EventsPublisher:
    """Monitor event directories and publish events."""

    def __init__(self, zkclient, app_events_dir=None, server_events_dir=None):
        self._zkclient = zkclient
        self._app_events_dir = app_events_dir
        self._server_events_dir = server_events_dir

        self._watcher = dirwatch.DirWatcher()
        self._dispatcher = dirwatch.DirWatcherDispatcher(self._watcher)

    def run(self):
        """Run events publisher."""
        if self._app_events_dir:
            self._configure(self._app_events_dir, app_zk.publish)
        if self._server_events_dir:
            self._configure(self._server_events_dir, server_zk.publish)

        while True:
            if self._watcher.wait_for_events(60):
                self._watcher.process_events()

    def _configure(self, events_dir, handler):
        self._watcher.add_dir(events_dir)
        self._dispatcher.register(events_dir, {
            dirwatch.DirWatcherEvent.CREATED:
                lambda p, h=handler: self._on_created(p, h)
        })
        for event_file in os.listdir(events_dir):
            path = os.path.join(events_dir, event_file)
            self._on_created(path, handler)

    @utils.exit_on_unhandled
    def _on_created(self, path, handler):
        if not os.path.exists(path):
            return

        event_dir, event_file = os.path.split(path)
        if event_file.startswith('.'):
            return

        _LOGGER.info('New event file - %s', path)

        when, what, event_type, event_data = event_file.split(',', 4)
        with io.open(path) as f:
            payload = f.read()

        handler(self._zkclient, when, what, event_type, event_data, payload)

        os.unlink(path)
