"""Treadmill lbendpoint REST API.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for lbendpoint resource."""

    namespace = webutils.namespace(
        api, __name__, 'LBEndpoint REST operations'
    )

    options = api.model('LBoptions', {
        'conn_timeout': fields.Integer(description='Connection timeout'),
        'lb_method': fields.String(description='Load balancing method'),
        'min_active': fields.Integer(description='Smallest number of '
                                     'active services before considering an '
                                     'outage in the pool'),
        'persist_type': fields.String(description='Persistence type'),
        'persist_timeout': fields.Integer(description='Persistence timeout'),
        'svc_down_action': fields.String(description='Service down action')
    })

    request_model = api.model('ReqLBendpoint', {
        '_id': fields.String(description='Name'),
        'endpoint': fields.String(description='App endpoint', required=True),
        'pattern': fields.String(description='App pattern', required=True),
        'port': fields.Integer(description='LB Port'),
        'cells': fields.List(fields.String(description='Cells')),
        'options': fields.Nested(options),
    })

    response_model = api.clone(
        'LBendpoint', request_model, {
            'environment': fields.String(
                description='App environment',
                enum=['dev', 'qa', 'uat', 'prod']
            ),
            'virtuals': fields.List(fields.String(description='LB Virtuals')),
            'vips': fields.List(fields.String(description='LB VIPs')),
        }
    )

    @namespace.route('/')
    class _LBEndpointList(restplus.Resource):
        """Treadmill LB Endpoint resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Return list of configured lbendpoints."""
            return impl.list()

    @namespace.route('/<lbendpoint_id>')
    @api.doc(params={'lbendpoint_id': 'LBEndpoint ID/name'})
    class _LBEndpointResource(restplus.Resource):
        """Treadmill lbendpoint resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, lbendpoint_id):
            """Return Treadmill lbendpoint configuration."""
            return impl.get(lbendpoint_id)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, lbendpoint_id):
            """Create Treadmill lbendpoint."""
            return impl.create(lbendpoint_id, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, lbendpoint_id):
            """Update Treadmill lbendpoint configuration."""
            return impl.update(lbendpoint_id, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, lbendpoint_id):
            """Delete Treadmill lbendpoint."""
            return impl.delete(lbendpoint_id)
