"""
A WebSocket handler for Treadmill trace.
"""

from __future__ import absolute_import

import os
import logging

from treadmill import schema
from treadmill.apptrace import events as traceevents
from treadmill.websocket import utils


_LOGGER = logging.getLogger(__name__)


class TraceAPI(object):
    """Handler for /trace topic."""

    def __init__(self, sow_db=None):
        """init"""
        self.sow_db = sow_db

        @schema.schema({'$ref': 'websocket/trace.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            parsed_filter = utils.parse_message_filter(message['filter'])

            return [(os.path.join('/tasks',
                                  parsed_filter.appname,
                                  parsed_filter.instanceid), '*')]

        def on_event(filename, _operation, content):
            """Event handler."""
            if not filename.startswith('/tasks/'):
                return

            appname, instanceid, info = filename[len('/tasks/'):].split('/', 2)
            timestamp, src_host, event_type, event_data = info.split(',', 3)

            event = traceevents.AppTraceEvent.from_data(
                timestamp=float(timestamp),
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

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init."""
    return [('/trace', TraceAPI(sow_db='.tasks-sow.db'))]
