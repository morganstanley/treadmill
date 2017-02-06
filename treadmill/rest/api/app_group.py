"""
Treadmill AppGroup REST api.
"""


import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for app_group resource."""

    namespace = webutils.namespace(
        api, __name__, 'AppGroup REST operations'
    )

    app_group_model = {
        '_id': fields.String(description='Name'),
        'cells': fields.List(fields.String(description='Cells')),
        'group-type': fields.String(description='Group Type'),
        'pattern': fields.String(description='Pattern'),
        'data': fields.String(description='Data'),
    }

    request_model = api.model(
        'ReqAppGroup', app_group_model
    )
    response_model = api.model(
        'RespAppGroup', app_group_model
    )

    @namespace.route(
        '/',
    )
    class _AppGroupList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Returns list of configured applications."""
            return impl.list()

    @namespace.route('/<app_group>')
    @api.doc(params={'app_group': 'App Group ID/name'})
    class _AppGroupResource(restplus.Resource):
        """Treadmill AppGroup resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, app_group):
            """Return Treadmill app-group configuration."""
            return impl.get(app_group)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, app_group):
            """Creates Treadmill app-group."""
            return impl.create(app_group, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, app_group):
            """Updates Treadmill app-group configuration."""
            return impl.update(app_group, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_group):
            """Deletes Treadmill app-group."""
            return impl.delete(app_group)
