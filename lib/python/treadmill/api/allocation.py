"""Implementation of allocation API."""
from __future__ import absolute_import

from .. import admin
from .. import authz
from .. import context
from .. import schema


def _unpack(rsrc_id):
    """Returns a tuple of the allocation id and cell if there's any"""
    return rsrc_id[0], rsrc_id[1] if len(rsrc_id) > 1 else None


class API(object):
    """Treadmill Allocation REST api."""

    def __init__(self):

        def _admin_alloc():
            """Lazily return admin object."""
            return admin.Allocation(context.GLOBAL.ldap.conn)

        def _admin_cell_alloc():
            """Lazily return admin object."""
            return admin.CellAllocation(context.GLOBAL.ldap.conn)

        def _list(rsrc_id):
            """List allocations."""
            allocation, _ = _unpack(rsrc_id)
            tnt, alloc = allocation.split('-')

            # tenants can have hierarchy so let's include the subtenants too
            if '*' not in tnt:
                tnt += '*'

            return _admin_alloc().list({'_id': '-'.join([tnt, alloc])})

        @schema.schema({'$ref': 'allocation.json#/resource_id'})
        def get(rsrc_id):
            """Get allocation configuration."""
            allocation, cell = _unpack(rsrc_id)
            if cell:
                return _admin_cell_alloc().get([cell, allocation])

            return _admin_alloc().get(allocation)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/create'}]})
        def create(rsrc_id, rsrc):
            """Create allocation."""
            allocation, cell = _unpack(rsrc_id)
            if cell:
                _admin_cell_alloc().create([cell, allocation], rsrc)
                return _admin_cell_alloc().get([cell, allocation])

            _admin_alloc().create(allocation, rsrc)
            return _admin_alloc().get(allocation)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/update'}]})
        def update(rsrc_id, rsrc):
            """Update allocation."""
            allocation, cell = _unpack(rsrc_id)
            if cell:
                _admin_cell_alloc().update([cell, allocation], rsrc)
                return _admin_cell_alloc().get([cell, allocation])

            _admin_alloc().update(allocation, rsrc)
            return _admin_alloc().get(allocation)

        @schema.schema({'$ref': 'allocation.json#/resource_id'})
        def delete(rsrc_id):
            """Delete allocation."""
            allocation, cell = _unpack(rsrc_id)
            if cell:
                _admin_cell_alloc().delete([cell, allocation])
                return None

            _admin_alloc().delete(allocation)
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
