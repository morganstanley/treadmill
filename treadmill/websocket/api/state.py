"""
A WebSocket handler for Treadmill state.
"""

import logging
import os

import yaml


_LOGGER = logging.getLogger(__name__)


class RunningAPI(object):
    """Handler for /running topic."""

    def subscribe(self, message):
        """Return filter based on message payload."""
        app_filter = message['filter']
        if '#' not in app_filter:
            app_filter += '#*'

        return [('/running', app_filter)]

    def on_event(self, filename, operation, content):
        """Event handler."""
        if operation == 'c':
            return

        if not filename.startswith('/running/'):
            return

        appname = os.path.basename(filename)
        return {
            'topic': '/running',
            'name': appname,
            'host': content,
        }


class ScheduledAPI(object):
    """Handler for /scheduled topic."""

    def subscribe(self, message):
        """Return filter based on message payload."""
        app_filter = message['filter']
        if app_filter.find('#') == -1:
            app_filter += '#*'

        return [('/scheduled', app_filter)]

    def on_event(self, filename, operation, content):
        """Event handler."""
        if operation == 'c':
            return

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


def init():
    """API module init."""
    return [
        ('/running', RunningAPI()),
        ('/scheduled', ScheduledAPI()),
    ]
