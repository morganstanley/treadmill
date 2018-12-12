"""Implementation of server API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import context
from treadmill import schema


class API:
    """Treadmill Server REST api."""

    def __init__(self):

        def _admin_svr():
            """Lazily return admin object."""
            return context.GLOBAL.admin.server()

        @schema.schema(
            cell={'anyOf': [
                {'type': 'null'},
                {'$ref': 'server.json#/resource/properties/cell'}
            ]},
            partition={'anyOf': [
                {'type': 'null'},
                {'$ref': 'server.json#/resource/properties/partition'}
            ]}
        )
        def _list(cell=None, partition=None):
            """List servers by cell and/or features."""
            filter_ = {}
            if cell:
                filter_['cell'] = cell

            result = _admin_svr().list(filter_)
            if partition:
                result = [x for x in result if
                          (x['partition'] == partition)]
            return result

        @schema.schema({'$ref': 'server.json#/resource_id'})
        def get(rsrc_id):
            """Get server configuration."""
            result = _admin_svr().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        @schema.schema({'$ref': 'server.json#/resource_id'},
                       {'allOf': [{'$ref': 'server.json#/resource'},
                                  {'$ref': 'server.json#/verbs/create'}]})
        def create(rsrc_id, rsrc):
            """Create server."""
            _admin_svr().create(rsrc_id, rsrc)
            return _admin_svr().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'server.json#/resource_id'},
                       {'allOf': [{'$ref': 'server.json#/resource'},
                                  {'$ref': 'server.json#/verbs/update'}]})
        def update(rsrc_id, rsrc):
            """Update server."""
            _admin_svr().update(rsrc_id, rsrc)
            return _admin_svr().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'server.json#/resource_id'})
        def delete(rsrc_id):
            """Delete server."""
            _admin_svr().delete(rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
