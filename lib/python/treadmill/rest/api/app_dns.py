"""Treadmill App DNS REST API.
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
    """Configures REST handlers for app-dns resource."""

    namespace = webutils.namespace(
        api, __name__, 'App DNS REST operations'
    )

    model = {
        '_id': fields.String(description='Name'),
        'cells': fields.List(fields.String(description='Cells')),
        'pattern': fields.String(description='App pattern'),
        'endpoints': fields.List(fields.String(description='Endpoints')),
        'alias': fields.String(description='Alias'),
        'scope': fields.String(description='Scope', required=True),
    }

    app_dns_model = api.model(
        'AppDNS', model
    )

    @namespace.route(
        '/',
    )
    class _AppDNSList(restplus.Resource):
        """Treadmill app-dns resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=app_dns_model)
        def get(self):
            """Returns list of configured app-dns."""
            return impl.list()

    @namespace.route('/<app_dns>')
    @api.doc(params={'app_dns': 'Application DNS ID/name'})
    class _AppDNSResource(restplus.Resource):
        """Treadmill App DNS resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=app_dns_model)
        def get(self, app_dns):
            """Return Treadmill app-dns configuration."""
            return impl.get(app_dns)

        @webutils.post_api(api, cors,
                           req_model=app_dns_model,
                           resp_model=app_dns_model)
        def post(self, app_dns):
            """Creates Treadmill app-dns."""
            return impl.create(app_dns, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=app_dns_model,
                          resp_model=app_dns_model)
        def put(self, app_dns):
            """Updates Treadmill app-dns configuration."""
            return impl.update(app_dns, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_dns):
            """Deletes Treadmill app-dns."""
            return impl.delete(app_dns)
