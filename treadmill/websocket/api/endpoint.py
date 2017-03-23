"""
A WebSocket handler for Treadmill state.
"""

import os
import logging


_LOGGER = logging.getLogger(__name__)


class EndpointAPI(object):
    """Handler for /endpoints topic."""

    def subscribe(self, message):
        """Return filter based on message payload."""
        app_filter = message['filter']
        proto = message.get('proto')
        if not proto:
            proto = '*'

        endpoint = message.get('endpoint')
        if not endpoint:
            endpoint = '*'

        proid, pattern = app_filter.split('.', 1)
        if '#' not in pattern:
            pattern += '#*'

        full_pattern = ':'.join([pattern, proto, endpoint])
        return [(os.path.join('/endpoints', proid), full_pattern)]

    def on_event(self, filename, operation, content):
        """Event handler."""
        if operation == 'c':
            return

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


def init():
    """API module init."""
    return [('/endpoints', EndpointAPI())]
