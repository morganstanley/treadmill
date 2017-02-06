"""
Treadmill Identity Group REST api.
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
    """Configures REST handlers for app monitor resource."""

    namespace = webutils.namespace(
        api, __name__, 'Identity Group REST operations'
    )

    identity_group_model = {
        '_id': fields.String(description='Name'),
        'count': fields.Integer(
            description='Identiy Group Count',
            required=True),
    }

    request_model = api.model(
        'ReqIdentityGroup', identity_group_model
    )
    response_model = api.model(
        'RespIdentityGroup', identity_group_model
    )

    @namespace.route(
        '/',
    )
    class _IdentityGroupList(restplus.Resource):
        """Treadmill identity group resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Returns list of configured identity groups."""
            return impl.list()

    @namespace.route('/<app_id>')
    @api.doc(params={'app_ip': 'App ID/name'})
    class _IdentityGroupResource(restplus.Resource):
        """Treadmill identity group resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, app_id):
            """Return identity group configuration."""
            return impl.get(app_id)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, app_id):
            """Creates identity group."""
            return impl.create(app_id, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, app_id):
            """Updates identity group configuration."""
            return impl.update(app_id, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_id):
            """Deletes identity group."""
            return impl.delete(app_id)
