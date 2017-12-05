"""Treadmill App REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus

from treadmill import webutils

from treadmill.api.model import app as app_model


def init(api, cors, impl):
    """Configures REST handlers for app resource."""

    namespace = webutils.namespace(
        api, __name__, 'Application REST operations'
    )

    request_model, response_model = app_model.models(api)

    match_parser = api.parser()
    match_parser.add_argument('match', help='A glob match on an app name',
                              location='args', required=False,)

    @namespace.route(
        '/',
    )
    class _AppList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model,
                          parser=match_parser)
        def get(self):
            """Returns list of configured applications."""
            args = match_parser.parse_args()
            return impl.list(args.get('match'))

    @namespace.route('/<app>')
    @api.doc(params={'app': 'Application ID/Name'})
    class _AppResource(restplus.Resource):
        """Treadmill App resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, app):
            """Return Treadmill application configuration."""
            return impl.get(app)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, app):
            """Creates Treadmill application."""
            return impl.create(app, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, app):
            """Updates Treadmill application configuration."""
            return impl.update(app, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app):
            """Deletes Treadmill application."""
            return impl.delete(app)
