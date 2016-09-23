"""
Treadmill allocation REST api.
"""
from __future__ import absolute_import
# pylint: disable=E0611,F0401
import flask
import flask.ext.restplus as restplus

from treadmill import webutils


def _alloc_id(tnt_id='*', alloc_name='*', cell=None):
    """Constructs allocation id for low level admin API."""
    alloc = '-'.join([tnt_id, alloc_name])
    if cell:
        return [alloc, cell]
    return [alloc]


# pylint: disable=W0232,R0912
def init(api, cors, impl):
    """Configures REST handlers for allocation resource."""

    namespace = api.namespace('allocation',
                              description='Allocation REST operations')

    @namespace.route('/',)
    class _AllocationsList(restplus.Resource):
        """Treadmill Allocation resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured allocations."""
            return impl.list(_alloc_id())

    @namespace.route('/<tnt_id>',)
    class _AllocationListForTenant(restplus.Resource):
        """Treadmill allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id):
            """Returns the list of the tenant's allocations."""
            return impl.list(_alloc_id(tnt_id))

    @namespace.route('/<tnt_id>/<alloc_id>',)
    class _AllocationResource(restplus.Resource):
        """Treadmill allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id, alloc_id):
            """Returns the allocation's details."""
            return impl.get(_alloc_id(tnt_id, alloc_id))

        @webutils.post_api(api, cors)
        def post(self, tnt_id, alloc_id):
            """Creates Treadmill allocation."""
            return impl.create(_alloc_id(tnt_id, alloc_id), flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, tnt_id, alloc_id):
            """Deletes Treadmill allocation."""
            return impl.delete(_alloc_id(tnt_id, alloc_id))

    @namespace.route('/<tnt_id>/<alloc_id>/<cell_id>',)
    class _CellAllocationResource(restplus.Resource):
        """Treadmill cell allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id, alloc_id, cell_id):
            """Returns the details of the allocation in the cell."""
            return impl.get(_alloc_id(tnt_id, alloc_id, cell_id))

        @webutils.post_api(api, cors)
        def post(self, tnt_id, alloc_id, cell_id):
            """Creates a Treadmill allocation in the cell."""
            return impl.create(
                _alloc_id(tnt_id, alloc_id, cell_id), flask.request.json)

        @webutils.put_api(api, cors)
        def put(self, tnt_id, alloc_id, cell_id):
            """Updates Treadmill allocation configuration."""
            return impl.update(
                _alloc_id(tnt_id, alloc_id, cell_id), flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, tnt_id, alloc_id, cell_id):
            """Deletes Treadmill allocation."""
            return impl.delete(_alloc_id(tnt_id, alloc_id, cell_id))
