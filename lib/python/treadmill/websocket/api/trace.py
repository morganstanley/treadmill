"""
A WebSocket handler for Treadmill trace.
"""

from __future__ import absolute_import

import logging

from treadmill import schema
from treadmill import zknamespace as z
from treadmill.apptrace import events as traceevents


_LOGGER = logging.getLogger(__name__)


class TraceAPI(object):
    """Handler for /trace topic."""

    def __init__(self, sow_db=None):
        """init"""
        self.sow_db = sow_db

        @schema.schema({'$ref': 'websocket/trace.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            instanceid = message['filter']
            subscription = [
                (z.path.trace(instanceid), '%s,*' % instanceid)
            ]
            _LOGGER.info('Addind trace subscription: %s', subscription)
            return subscription

        def on_event(filename, _operation, content):
            """Event handler."""
            if not filename.startswith('/trace/'):
                return

            _shard, event = filename[len('/trace/'):].split('/')
            (instanceid,
             timestamp,
             src_host,
             event_type,
             event_data) = event.split(',', 4)

            trace_event = traceevents.AppTraceEvent.from_data(
                timestamp=float(timestamp),
                source=src_host,
                instanceid=instanceid,
                event_type=event_type,
                event_data=event_data,
                payload=content
            )
            if trace_event is None:
                return

            return {
                'topic': '/trace',
                'event': trace_event.to_dict()
            }

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init."""
    return [('/trace', TraceAPI(sow_db='.trace-sow.db'))]
