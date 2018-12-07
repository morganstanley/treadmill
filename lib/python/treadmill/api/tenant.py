"""Implementation of tenant API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import context
from treadmill import schema


class API:
    """Treadmill Tenant REST api."""

    def __init__(self):

        def _admin_tnt():
            """Lazily return admin object."""
            return context.GLOBAL.admin.tenant()

        def _list():
            """List tenants."""
            return sorted(_admin_tnt().list({}), key=lambda x: x['tenant'])

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
            return _admin_tnt().get(rsrc_id, dirty=True)

        @schema.schema(
            {'$ref': 'tenant.json#/resource_id'},
            {'allOf': [{'$ref': 'tenant.json#/resource'},
                       {'$ref': 'tenant.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update tenant."""
            _admin_tnt().update(rsrc_id, rsrc)
            return _admin_tnt().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'tenant.json#/resource_id'})
        def delete(rsrc_id):
            """Delete tenant."""
            _admin_tnt().delete(rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
