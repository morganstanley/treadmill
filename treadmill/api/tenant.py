"""Implementation of tenant API."""


from .. import admin
from .. import authz
from .. import context
from .. import schema


class API(object):
    """Treadmill Tenant REST api."""

    def __init__(self):

        def _admin_tnt():
            """Lazily return admin object."""
            return admin.Tenant(context.GLOBAL.ldap.conn)

        def _list():
            """List tenants."""
            return _admin_tnt().list({})

        @schema.schema({'$ref': 'tenant.json#/resource_id'})
        def get(rsrc_id):
            """Get tenant configuration."""
            result = _admin_tnt().get(rsrc_id)
            result['_id'] = rsrc_id
            del result['tenant']
            return result

        @schema.schema(
            {'$ref': 'tenant.json#/resource_id'},
            {'allOf': [{'$ref': 'tenant.json#/resource'},
                       {'$ref': 'tenant.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create tenant."""
            _admin_tnt().create(rsrc_id, rsrc)
            return _admin_tnt().get(rsrc_id)

        @schema.schema(
            {'$ref': 'tenant.json#/resource_id'},
            {'allOf': [{'$ref': 'tenant.json#/resource'},
                       {'$ref': 'tenant.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update tenant."""
            _admin_tnt().update(rsrc_id, rsrc)
            return _admin_tnt().get(rsrc_id)

        @schema.schema({'$ref': 'tenant.json#/resource_id'})
        def delete(rsrc_id):
            """Delete tenant."""
            _admin_tnt().delete(rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
