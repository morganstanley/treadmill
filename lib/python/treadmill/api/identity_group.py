"""Implementation of identity group API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import fnmatch

from treadmill import context
from treadmill import schema
from treadmill.scheduler import masterapi


_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill Identity Group REST api."""

    def __init__(self):

        def _list(match=None):
            """List configured identity groups."""
            if match is None:
                match = '*'

            zkclient = context.GLOBAL.zk.conn
            groups = [
                masterapi.get_identity_group(zkclient, group)
                for group in masterapi.identity_groups(zkclient)
            ]

            filtered = [
                group for group in groups
                if group is not None and fnmatch.fnmatch(group['_id'], match)
            ]
            return sorted(filtered, key=lambda item: item['_id'])

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
        )
        def get(rsrc_id):
            """Get application group configuration."""
            zkclient = context.GLOBAL.zk.conn
            return masterapi.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
            {'allOf': [{'$ref': 'identity_group.json#/resource'},
                       {'$ref': 'identity_group.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application group."""
            zkclient = context.GLOBAL.zk.conn
            masterapi.update_identity_group(zkclient, rsrc_id, rsrc['count'])
            return masterapi.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
            {'allOf': [{'$ref': 'identity_group.json#/resource'},
                       {'$ref': 'identity_group.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            zkclient = context.GLOBAL.zk.conn
            masterapi.update_identity_group(zkclient, rsrc_id, rsrc['count'])
            return masterapi.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
        )
        def delete(rsrc_id):
            """Delete configured application group."""
            zkclient = context.GLOBAL.zk.conn
            masterapi.delete_identity_group(zkclient, rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
