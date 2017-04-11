"""
A WebSocket handler for Treadmill state.
"""

from __future__ import absolute_import

import os
import logging

from treadmill import schema


_LOGGER = logging.getLogger(__name__)


class EndpointAPI(object):
    """Handler for /endpoints topic."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'websocket/endpoint.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            app_filter = message['filter']
            proto = message.get('proto') or '*'
            endpoint = message.get('endpoint') or '*'

            proid, pattern = app_filter.split('.', 1)
            if '#' not in pattern:
                pattern += '#*'

            full_pattern = ':'.join([pattern, proto, endpoint])
            return [(os.path.join('/endpoints', proid), full_pattern)]

        def on_event(filename, operation, content):
            """Event handler."""
            if not filename.startswith('/endpoints/'):
                return

            proid, endpoint_file = filename[len('/endpoints/'):].split('/', 1)

            host = None
            port = None
            if content is not None:
                host, port = content.split(':')
            sow = operation is None

            app, proto, endpoint = endpoint_file.split(':')
            return {
                'topic': '/endpoints',
                'name': '.'.join([proid, app]),
                'proto': proto,
                'endpoint': endpoint,
                'host': host,
                'port': port,
                'sow': sow,
            }

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init."""
    return [('/endpoints', EndpointAPI())]
