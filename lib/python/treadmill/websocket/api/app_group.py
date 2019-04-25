"""A WebSocket handler for Treadmill app_groups
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill import schema
from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)


_TOPIC = '/app-groups'
_SUB_DIR = '/app-groups'


class AppGroupAPI:
    """Handler for /app-groups topic.
    """

    def __init__(self):
        """constructor of API class
        """

        @schema.schema({'$ref': 'websocket/app_group.json#/message'})
        def subscribe(message):
            """Return filter based on message payload.
            """
            app_group = message.get('app-group', '*')

            return [(_SUB_DIR, app_group)]

        def on_event(filename, operation, content):
            """Event handler.
            """
            if not filename.startswith('{}/'.format(_SUB_DIR)):
                return None

            app_group = os.path.basename(filename)

            sow = operation is None
            message = {
                'topic': _TOPIC,
                'app-group': app_group,
                'sow': sow
            }

            if content:
                app_group_data = yaml.load(content)
                raw_data = app_group_data.pop('data', [])
                message.update(app_group_data)

                data = {}
                for kv_str in raw_data:
                    (key, val) = kv_str.split('=', 1)
                    data[key] = val

                message['data'] = data

            return message

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init.
    """
    return [(_TOPIC, AppGroupAPI(), [])]
