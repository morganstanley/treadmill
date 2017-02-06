"""
Treadmill App REST api.
"""


import flask
import flask_restplus as restplus

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611

from treadmill.api.model import app as app_model


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for app resource."""

    namespace = webutils.namespace(
        api, __name__, 'Application REST operations'
    )

    request_model, response_model = app_model.models(api)

    @namespace.route(
        '/',
    )
    class _AppList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Returns list of configured applications."""
            ret = impl.list()
            return ret

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
