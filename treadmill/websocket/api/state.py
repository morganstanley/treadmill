"""
A WebSocket handler for Treadmill state.
"""

import logging
import os
import yaml

from treadmill import schema
from treadmill.websocket import utils


_LOGGER = logging.getLogger(__name__)


class RunningAPI(object):
    """Handler for /running topic."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'websocket/state.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            parsed_filter = utils.parse_message_filter(message['filter'])

            return [('/running', parsed_filter.filter)]

        def on_event(filename, _operation, content):
            """Event handler."""
            if not filename.startswith('/running/'):
                return

            appname = os.path.basename(filename)
            return {
                'topic': '/running',
                'name': appname,
                'host': content,
            }

        self.subscribe = subscribe
        self.on_event = on_event


class ScheduledAPI(object):
    """Handler for /scheduled topic."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'websocket/state.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            parsed_filter = utils.parse_message_filter(message['filter'])

            return [('/scheduled', parsed_filter.filter)]

        def on_event(filename, _operation, content):
            """Event handler."""
            if not filename.startswith('/scheduled/'):
                return

            appname = os.path.basename(filename)
            manifest = None
            if content:
                manifest = yaml.load(content)

            return {
                'topic': '/scheduled',
                'name': appname,
                'manifest': manifest,
            }

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init."""
    return [
        ('/running', RunningAPI(), []),
        ('/scheduled', ScheduledAPI(), []),
    ]
