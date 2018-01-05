"""Treadmill Allocation-group REST API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for allocation-group resource."""

    namespace = webutils.namespace(
        api, __name__, 'Allocation-group REST operations'
    )

    model = api.model('Allocation-group', {
        'name': fields.String(description='Name'),
        'eonid': fields.String(description='Eonid'),
        'environment': fields.String(description='Environment'),
        'admins': fields.List(fields.String(description='Admins')),
        'owners': fields.List(fields.String(description='Owners')),
    })

    @namespace.route('/<group>')
    @api.doc(params={'group': 'Allocation-group name'})
    class _AllocationGroupResource(restplus.Resource):
        """Treadmill Allocation-group resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=model)
        def get(self, group):
            """Return Treadmill allocation-group configuration."""
            return impl.get(group)

        @webutils.post_api(api, cors,
                           req_model=model,
                           resp_model=model)
        def post(self, group):
            """Creates Treadmill allocation-group."""
            return impl.create(group, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=model,
                          resp_model=model)
        def put(self, group):
            """Updates Treadmill allocation-group configuration."""
            return impl.update(group, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, group):
            """Deletes Treadmill allocation-group."""
            return impl.delete(group)
