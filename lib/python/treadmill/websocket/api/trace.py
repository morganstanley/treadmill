"""A WebSocket handler for Treadmill trace.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import schema
from treadmill.trace.app import events as app_events
from treadmill.trace.app import zk as app_zk
from treadmill.websocket import _utils

_LOGGER = logging.getLogger(__name__)


class TraceAPI:
    """Handler for /trace topic.
    """

    def __init__(self):
        self.sow = app_zk.TRACE_SOW_DIR
        self.sow_table = app_zk.TRACE_SOW_TABLE

        @schema.schema({'$ref': 'websocket/trace.json#/message'})
        def subscribe(message):
            """Return filter based on message payload.
            """
            parsed_filter = _utils.parse_message_filter(message['filter'])
            subscription = [('/trace/*', '%s,*' % parsed_filter.filter)]
            _LOGGER.info('Adding trace subscription: %s', subscription)
            return subscription

        def on_event(filename, operation, content):
            """Event handler.
            """
            if not filename.startswith('/trace/'):
                return None

            # Ignore deletes for trace files, as they are not real events.
            if operation == 'd':
                return None

            _shard, event = filename[len('/trace/'):].split('/')
            (instanceid,
             timestamp,
             src_host,
             event_type,
             event_data) = event.split(',', 4)

            trace_event = app_events.AppTraceEvent.from_data(
                timestamp=float(timestamp),
                source=src_host,
                instanceid=instanceid,
                event_type=event_type,
                event_data=event_data,
                payload=content
            )
            if trace_event is None:
                return None

            return {
                'topic': '/trace',
                'event': trace_event.to_dict()
            }

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init.
    """
    return [('/trace', TraceAPI(), ['/trace/*'])]
