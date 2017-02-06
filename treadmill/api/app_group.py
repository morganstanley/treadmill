"""Implementation of AppGroup API"""


from .. import context
from .. import schema
from .. import authz
from .. import admin


class API(object):
    """Treadmill AppGroup REST api."""

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin object."""
            return admin.AppGroup(context.GLOBAL.ldap.conn)

        @schema.schema({'$ref': 'app_group.json#/resource_id'})
        def get(rsrc_id):
            """Get application configuration."""
            result = _admin_app_group().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        @schema.schema(
            {'$ref': 'app_group.json#/resource_id'},
            {'allOf': [{'$ref': 'app_group.json#/resource'},
                       {'$ref': 'app_group.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application."""
            _admin_app_group().create(rsrc_id, rsrc)
            return _admin_app_group().get(rsrc_id)

        @schema.schema(
            {'$ref': 'app_group.json#/resource_id'},
            {'allOf': [{'$ref': 'app_group.json#/resource'},
                       {'$ref': 'app_group.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            _admin_app_group().replace(rsrc_id, rsrc)
            return _admin_app_group().get(rsrc_id)

        @schema.schema({'$ref': 'app_group.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app_group().delete(rsrc_id)
            return None

        def _list():
            """List configured applications."""
            return _admin_app_group().list({})

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.list = _list


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
