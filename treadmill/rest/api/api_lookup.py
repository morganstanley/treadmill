"""Treadmill API Lookup REST API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils
from treadmill.api import api_lookup


def init(api, cors, impl):
    """Configures REST handlers for api_lookup resource"""

    namespace = api.namespace('api-lookup',
                              description='API Lookup REST operations')

    target_model = api.model('SRVTarget', {
        'host': fields.String(description='Host'),
        'port': fields.Integer(description='Port'),
        'priority': fields.Integer(description='Priority'),
        'weight': fields.Integer(description='Weight')
    })

    model = api.model('APILookup', {
        'targets': fields.List(fields.Nested(target_model))
    })

    @api.errorhandler(api_lookup.NoSuchCellException)
    def _handle_no_srv_records(exception):
        """Handle NoSuchCellException exception"""
        return vars(exception), 404

    @namespace.route('/adminapi')
    class _AdminApiLookupResource(restplus.Resource):
        """Treadmill Admin API Lookup resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=model)
        def get(self):
            """Returns list of SRV records for Admin API"""
            return impl.adminapi.get()

    @namespace.route('/cellapi/<cellname>')
    @api.doc(params={'cellname': 'Cell name'})
    class _CellApiLookupResource(restplus.Resource):
        """Treadmill Cell API Lookup resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=model)
        def get(self, cellname):
            """Returns list of SRV records for Cell API"""
            return impl.cellapi.get(cellname)

    @namespace.route('/stateapi/<cellname>')
    @api.doc(params={'cellname': 'Cell name'})
    class _StateApiLookupResource(restplus.Resource):
        """Treadmill State API Lookup resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=model)
        def get(self, cellname):
            """Returns list of SRV records for State API"""
            return impl.stateapi.get(cellname)

    @namespace.route('/wsapi/<cellname>')
    @api.doc(params={'cellname': 'Cell name'})
    class _WsApiLookupResource(restplus.Resource):
        """Treadmill WS API Lookup resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=model)
        def get(self, cellname):
            """Returns list of SRV records for WS API"""
            return impl.wsapi.get(cellname)
