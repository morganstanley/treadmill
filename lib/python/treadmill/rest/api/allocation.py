"""Treadmill allocation REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def _alloc_id(tenant, alloc, cell=None):
    """Constructs allocation id from tenant, name and optional cell."""
    if cell:
        return '%s/%s/%s' % (tenant, alloc, cell)
    else:
        return '%s/%s' % (tenant, alloc)


def init(api, cors, impl):
    """Configures REST handlers for allocation resource."""

    namespace = api.namespace('allocation',
                              description='Allocation REST operations')

    assignment = api.model('Assignment', {
        'priority': fields.Integer(description='Priority'),
        'pattern': fields.String(description='App pattern'),
    })
    reservation = api.model('Reservation', {
        '_id': fields.String(description='Name'),
        'memory': fields.String(description='Memory'),
        'cpu': fields.String(description='CPU'),
        'disk': fields.String(description='Disk size'),
        'rank': fields.Integer(description='App rank'),
        'rank_adjustment': fields.Integer(description='Rank adjustment.'),
        'max_utilization': fields.Float(description='Maximum utilization.'),
        'cell': fields.String(description='Cell'),
        'partition': fields.String(description='Partition'),
        'traits': fields.List(fields.String(description='Traits')),
        'assignments': fields.List(fields.Nested(assignment)),
    })
    model = {
        '_id': fields.String(description='Name'),
        'environment': fields.String(
            description='App environment',
            enum=['dev', 'qa', 'uat', 'prod'],
            required=True),
        'reservations': fields.List(fields.Nested(reservation)),
    }

    allocation_model = api.model(
        'Allocation', model
    )

    @namespace.route('/')
    class _AllocationsList(restplus.Resource):
        """Treadmill Allocation resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=allocation_model)
        def get(self):
            """Returns list of configured allocations."""
            return impl.list()

    @namespace.route('/<tenant_id>',)
    @api.doc(params={'tenant_id': 'Tenant ID/name'})
    class _AllocationListForTenant(restplus.Resource):
        """Treadmill allocation resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=allocation_model)
        def get(self, tenant_id):
            """Returns the list of the tenant's allocations."""
            return impl.list(tenant_id)

    @namespace.route('/<tenant_id>/<alloc_id>',)
    @api.doc(params={
        'tenant_id': 'Tenant ID/name',
        'alloc_id': 'Alloc ID/name',
    })
    class _AllocationResource(restplus.Resource):
        """Treadmill allocation resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=allocation_model)
        def get(self, tenant_id, alloc_id):
            """Returns the allocation's details."""
            return impl.get(_alloc_id(tenant_id, alloc_id))

        @webutils.post_api(api, cors,
                           req_model=allocation_model,
                           resp_model=allocation_model)
        def post(self, tenant_id, alloc_id):
            """Creates Treadmill allocation."""
            return impl.create(
                _alloc_id(tenant_id, alloc_id), flask.request.json
            )

        @webutils.delete_api(api, cors)
        def delete(self, tenant_id, alloc_id):
            """Deletes Treadmill allocation."""
            return impl.delete(_alloc_id(tenant_id, alloc_id))

    @namespace.route('/<tenant_id>/<alloc_id>/reservation/<cell>',)
    @api.doc(params={
        'tenant_id': 'Tenant ID/name',
        'alloc_id': 'Alloc ID/name',
        'cell': 'Cell name',
    })
    class _ReservationResource(restplus.Resource):
        """Treadmill cell allocation resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=reservation)
        def get(self, tenant_id, alloc_id, cell):
            """Returns the details of the reservation."""
            return impl.reservation.get('/'.join([tenant_id, alloc_id, cell]))

        @webutils.post_api(api, cors,
                           req_model=reservation,
                           resp_model=reservation)
        def post(self, tenant_id, alloc_id, cell):
            """Creates a Treadmill reservation in the cell."""
            return impl.reservation.create(
                '/'.join([tenant_id, alloc_id, cell]),
                flask.request.json
            )

        @webutils.put_api(api, cors,
                          req_model=reservation,
                          resp_model=reservation)
        def put(self, tenant_id, alloc_id, cell):
            """Updates Treadmill reservation configuration."""
            return impl.reservation.update(
                '/'.join([tenant_id, alloc_id, cell]),
                flask.request.json
            )

        @api.hide
        @webutils.delete_api(api, cors)
        def delete(self, tenant_id, alloc_id, cell):
            """Deletes Treadmill allocation."""
            return impl.reservation.delete(
                '/'.join([tenant_id, alloc_id, cell])
            )

    @namespace.route('/<tenant_id>/<alloc_id>/assignment/<cell>/<pattern>',)
    @api.doc(responses={404: 'Not found'})
    @api.doc(params={
        'tenant_id': 'Tenant ID/name',
        'alloc_id': 'Alloc ID/name',
        'cell': 'Cell name',
        'pattern': 'App pattern',
    })
    class _AssignmentResource(restplus.Resource):
        """Treadmill cell allocation resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=assignment)
        def get(self, tenant_id, alloc_id, cell, pattern):
            """Returns the details of the reservation."""
            return impl.assignment.get(
                '/'.join([tenant_id, alloc_id, cell, pattern])
            )

        @webutils.post_api(api, cors,
                           req_model=assignment,
                           resp_model=assignment)
        def post(self, tenant_id, alloc_id, cell, pattern):
            """Creates a Treadmill reservation in the cell."""
            return impl.assignment.create(
                '/'.join([tenant_id, alloc_id, cell, pattern]),
                flask.request.json
            )

        @webutils.put_api(api, cors,
                          req_model=assignment,
                          resp_model=assignment)
        def put(self, tenant_id, alloc_id, cell, pattern):
            """Updates Treadmill allocation assignment."""
            return impl.assignment.update(
                '/'.join([tenant_id, alloc_id, cell, pattern]),
                flask.request.json
            )

        @webutils.delete_api(api, cors)
        def delete(self, tenant_id, alloc_id, cell, pattern):
            """Deletes Treadmill allocation assignment."""
            return impl.assignment.delete(
                '/'.join([tenant_id, alloc_id, cell, pattern])
            )
