"""A WebSocket handler for Treadmill state.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import schema
from treadmill import yamlwrapper as yaml


_LOGGER = logging.getLogger(__name__)


class IdentityGroupAPI:
    """Handler for /identity-groups topic.
    """

    def __init__(self):
        @schema.schema({'$ref': 'websocket/identity_group.json#/message'})
        def subscribe(message):
            """Return filter based on message payload.
            """
            identity_group = message.get('identity-group', '*')

            return [('/'.join(['/identity-groups', identity_group]), '*')]

        def on_event(filename, operation, content):
            """Event handler.
            """
            if not filename.startswith('/identity-groups/'):
                return None

            sow = operation is None

            full_identity = filename[len('/identity-groups/'):]
            identity_group, identity = full_identity.rsplit('/', 1)
            message = {
                'topic': '/identity-groups',
                'identity-group': identity_group,
                'identity': int(identity),
                'app': None,
                'host': None,
                'sow': sow
            }
            if content:
                message.update(yaml.load(content))

            return message

        self.subscribe = subscribe
        self.on_event = on_event


def init():
    """API module init.
    """
    return [('/identity-groups', IdentityGroupAPI(), [])]
