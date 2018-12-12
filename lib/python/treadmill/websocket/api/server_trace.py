"""A WebSocket handler for Treadmill trace.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import schema
from treadmill.trace.server import events as server_events
from treadmill.trace.server import zk as server_zk

_LOGGER = logging.getLogger(__name__)


class ServerTraceAPI:
    """Handler for /server-trace topic.
    """

    def __init__(self):
        self.sow = server_zk.SERVER_TRACE_SOW_DIR
        self.sow_table = server_zk.SERVER_TRACE_SOW_TABLE

        @schema.schema({'$ref': 'websocket/server_trace.json#/message'})
        def subscribe(message):
            """Return filter based on message payload.
            """
            subscription = [('/server-trace/*', '%s,*' % message['filter'])]
            _LOGGER.info('Adding server trace subscription: %s', subscription)
            return subscription

        def on_event(filename, operation, content):
            """Event handler.
            """
            if not filename.startswith('/server-trace/'):
                return None

            # Ignore deletes for trace files, as they are not real events.
            if operation == 'd':
                return None

            _shard, event = filename[len('/server-trace/'):].split('/')
            (servername,
             timestamp,
             src_host,
             event_type,
             event_data) = event.split(',', 4)

            trace_event = server_events.ServerTraceEvent.from_data(
                timestamp=float(timestamp),
                source=src_host,
                servername=servername,
                event_type=event_type,
                event_data=event_data,
                payload=content
            )
            if trace_event is None:
                return None

            return {
                'topic': '/server-trace',
                'event': trace_event.to_dict()
            }

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init.
    """
    return [('/server-trace', ServerTraceAPI(), [])]
