"""A WebSocket handler for Treadmill state.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import schema
from treadmill.websocket import _utils

_LOGGER = logging.getLogger(__name__)


class EndpointAPI:
    """Handler for /endpoints topic."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'websocket/endpoint.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            parsed_filter = _utils.parse_message_filter(message['filter'])
            if '.' not in parsed_filter.filter:
                raise ValueError('Invalid filter: expect proid.pattern')
            proid, pattern = parsed_filter.filter.split('.', 1)

            proto = message.get('proto', '*')
            endpoint = message.get('endpoint', '*')

            full_pattern = ':'.join([pattern, proto, endpoint])
            return [('/'.join(['/endpoints', proid]), full_pattern)]

        def on_event(filename, operation, content):
            """Event handler."""
            if not filename.startswith('/endpoints/'):
                return None

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
    return [('/endpoints', EndpointAPI(), [])]
