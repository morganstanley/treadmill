"""Treadmill lbendpoint-tm2 REST API.
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
    """Configures REST handlers for lbendpoint-tm2 resource."""

    namespace = webutils.namespace(
        api, __name__, 'LBEndpoint TM2 REST operations'
    )

    request_model = api.model('ReqLBEndpointTM2', {
        '_id': fields.String(description='Name'),
        'endpoint': fields.String(description='App endpoint'),
        'pattern': fields.String(description='App pattern'),
        'cells': fields.List(fields.String(description='Cells')),
    })

    response_model = api.clone(
        'LBEndpointTM2', request_model, {
            'vip': fields.String(description='VIP'),
            'port': fields.Integer(description='Port'),
            'location': fields.String(description='Location'),
        }
    )

    @namespace.route('/')
    class _LBEndpointTM2List(restplus.Resource):
        """Treadmill lbendpoint-tm2 resource list."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """List TM2 lbendpoints."""
            return impl.list()

    @namespace.route('/<lbendpoint_id>')
    @api.doc(params={'lbendpoint_id': 'LBEndpoint ID/name'})
    class _LBEndpointTM2Resource(restplus.Resource):
        """Treadmill lbendpoint-tm2 resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, lbendpoint_id):
            """Get TM2 lbendpoint."""
            return impl.get(lbendpoint_id)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, lbendpoint_id):
            """Update TM2 lbendpoint."""
            return impl.update(lbendpoint_id, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, lbendpoint_id):
            """Delete TM2 lbendpoint and virtual/pool."""
            return impl.delete(lbendpoint_id)
