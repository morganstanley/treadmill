"""
A WebSocket handler for Treadmill trace.
"""

import os
import logging

from treadmill.apptrace import events as traceevents

_LOGGER = logging.getLogger(__name__)


class TraceAPI(object):
    """Handler for /trace topic."""

    def subscribe(self, message):
        """Return filter based on message payload."""
        app_filter = message['filter']

        if '#' not in app_filter:
            app_filter += '#*'

        app_name, instanceid = app_filter.split('#', 1)

        return [(os.path.join('/tasks', app_name, instanceid), '*')]

    def on_event(self, filename, operation, content):
        """Event handler.
        """
        if operation == 'c':
            return

        if not filename.startswith('/tasks/'):
            return

        appname, instanceid, info = filename[len('/tasks/'):].split('/', 2)
        timestamp, src_host, event_type, event_data = info.split(',', 3)

        event = traceevents.AppTraceEvent.from_data(
            timestamp=timestamp,
            source=src_host,
            instanceid='{appname}#{instanceid}'.format(
                appname=appname,
                instanceid=instanceid
            ),
            event_type=event_type,
            event_data=event_data,
            payload=content
        )
        if event is None:
            return

        return {
            'topic': '/trace',
            'event': event.to_dict()
        }


def init():
    """API module init."""
    return [('/trace', TraceAPI())]
