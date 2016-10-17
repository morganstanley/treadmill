"""
Treadmill allocation REST api.
"""
from __future__ import absolute_import
# pylint: disable=E0611,F0401
import flask
import flask.ext.restplus as restplus

from treadmill import webutils


def _alloc_id(tenant, alloc, cell=None):
    """Constructs allocation id from tenant, name and optional cell."""
    if cell:
        return '%s/%s/%s' % (tenant, alloc, cell)
    else:
        return '%s/%s' % (tenant, alloc)


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
            return impl.list()

    @namespace.route('/<tnt_id>',)
    class _AllocationListForTenant(restplus.Resource):
        """Treadmill allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id):
            """Returns the list of the tenant's allocations."""
            return impl.list(tnt_id)

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

    @namespace.route('/<tnt_id>/<alloc_id>/reservation/<cell_id>',)
    class _ReservationResource(restplus.Resource):
        """Treadmill cell allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id, alloc_id, cell_id):
            """Returns the details of the reservation."""
            return impl.reservation.get('/'.join([tnt_id, alloc_id, cell_id]))

        @webutils.post_api(api, cors)
        def post(self, tnt_id, alloc_id, cell_id):
            """Creates a Treadmill reservation in the cell."""
            return impl.reservation.create(
                '/'.join([tnt_id, alloc_id, cell_id]),
                flask.request.json
            )

        @webutils.put_api(api, cors)
        def put(self, tnt_id, alloc_id, cell_id):
            """Updates Treadmill reservation configuration."""
            return impl.reservation.update(
                '/'.join([tnt_id, alloc_id, cell_id]),
                flask.request.json
            )

        @webutils.delete_api(api, cors)
        def delete(self, tnt_id, alloc_id, cell_id):
            """Deletes Treadmill allocation."""
            del tnt_id
            del alloc_id
            del cell_id
            raise Exception('Not implemented.')

    @namespace.route('/<tnt_id>/<alloc_id>/assignment/<cell_id>/<pattern>',)
    class _AssignmentResource(restplus.Resource):
        """Treadmill cell allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, tnt_id, alloc_id, cell_id, pattern):
            """Returns the details of the reservation."""
            return impl.assignment.get(
                '/'.join([tnt_id, alloc_id, cell_id, pattern])
            )

        @webutils.post_api(api, cors)
        def post(self, tnt_id, alloc_id, cell_id, pattern):
            """Creates a Treadmill reservation in the cell."""
            return impl.assignment.create(
                '/'.join([tnt_id, alloc_id, cell_id, pattern]),
                flask.request.json
            )

        @webutils.put_api(api, cors)
        def put(self, tnt_id, alloc_id, cell_id, pattern):
            """Updates Treadmill allocation assignment."""
            return impl.assignment.update(
                '/'.join([tnt_id, alloc_id, cell_id, pattern]),
                flask.request.json
            )

        @webutils.delete_api(api, cors)
        def delete(self, tnt_id, alloc_id, cell_id, pattern):
            """Deletes Treadmill allocation assignment."""
            return impl.assignment.delete(
                '/'.join([tnt_id, alloc_id, cell_id, pattern])
            )
