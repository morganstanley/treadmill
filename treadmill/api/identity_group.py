"""Implementation of identity group API."""


import logging

from .. import context
from .. import schema
from .. import authz
from .. import master


_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill Identity Group REST api."""

    def __init__(self):

        def _list():
            """List configured identity groups."""
            zkclient = context.GLOBAL.zk.conn
            groups = [
                master.get_identity_group(zkclient, group)
                for group in master.identity_groups(zkclient)
            ]
            return [group for group in groups if group is not None]

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
        )
        def get(rsrc_id):
            """Get application monitor configuration."""
            zkclient = context.GLOBAL.zk.conn
            return master.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
            {'allOf': [{'$ref': 'identity_group.json#/resource'},
                       {'$ref': 'identity_group.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application monitor."""
            zkclient = context.GLOBAL.zk.conn
            master.update_identity_group(zkclient, rsrc_id, rsrc['count'])
            return master.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
            {'allOf': [{'$ref': 'identity_group.json#/resource'},
                       {'$ref': 'identity_group.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            zkclient = context.GLOBAL.zk.conn
            master.update_identity_group(zkclient, rsrc_id, rsrc['count'])
            return master.get_identity_group(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'identity_group.json#/resource_id'},
        )
        def delete(rsrc_id):
            """Delete configured application monitor."""
            zkclient = context.GLOBAL.zk.conn
            master.delete_identity_group(zkclient, rsrc_id)
            return None

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
