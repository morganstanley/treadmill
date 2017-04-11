"""
A WebSocket handler for Treadmill state.
"""

from __future__ import absolute_import

import logging
import os
import yaml

from treadmill import schema


_LOGGER = logging.getLogger(__name__)


class RunningAPI(object):
    """Handler for /running topic."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'websocket/state.json#/message'})
        def subscribe(message):
            """Return filter based on message payload."""
            app_filter = message['filter']
            if '#' not in app_filter:
                app_filter += '#*'

            return [('/running', app_filter)]

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
            app_filter = message['filter']
            if app_filter.find('#') == -1:
                app_filter += '#*'

            return [('/scheduled', app_filter)]

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
        ('/running', RunningAPI()),
        ('/scheduled', ScheduledAPI()),
    ]
