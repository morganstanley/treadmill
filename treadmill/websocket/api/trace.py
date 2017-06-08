"""A WebSocket handler for Treadmill trace.
"""

import logging

from treadmill import apptrace
from treadmill import schema
from treadmill.websocket import utils
from treadmill.apptrace import events as traceevents


_LOGGER = logging.getLogger(__name__)


class TraceAPI(object):
    """Handler for /trace topic."""

    def __init__(self, sow=None):
        """init"""
        self.sow = sow
        self.sow_table = 'trace'

        @schema.schema({'$ref': 'websocket/trace.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            parsed_filter = utils.parse_message_filter(message['filter'])
            subscription = [('/trace/*', '%s,*' % parsed_filter.filter)]
            _LOGGER.info('Adding trace subscription: %s', subscription)
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
    return [('/trace', TraceAPI(sow=apptrace.TRACE_SOW_DIR), ['/trace/*'])]
