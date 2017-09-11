"""
Treadmill IPA REST api.
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
    """Configures REST handlers for ipa resource."""

    namespace = webutils.namespace(
        api, __name__, 'IPA REST operations'
    )

    service_req_model = {
        'service': fields.String(description='Service Name'),
        'hostname': fields.String(description='Hostname'),
        'domain': fields.String(description='Domain')
    }

    service_model = api.model(
        'service', service_req_model
    )

    host_req_model = {
        'hostname': fields.String(description='Hostname'),
    }

    host_model = api.model(
        'host', host_req_model
    )

    user_req_model = {
        'username': fields.String(description='Username'),
    }

    user_model = api.model(
        'user', user_req_model
    )

    @namespace.route('/host')
    class _Host(restplus.Resource):
        """Treadmill IPA Host"""

        @webutils.post_api(
            api,
            cors,
            req_model=host_model
        )
        def post(self):
            """Adds host to IPA."""
            return impl.add_host(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=host_model
        )
        def delete(self):
            """Deletes host from IPA."""
            return impl.delete_host(flask.request.json)

    @namespace.route('/user')
    class _User(restplus.Resource):
        """Treadmill IPA User"""

        @webutils.post_api(
            api,
            cors,
            req_model=user_model
        )
        def post(self):
            """Adds User to IPA."""
            return impl.add_user(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=user_model
        )
        def delete(self):
            """Deletes User from IPA."""
            return impl.delete_user(flask.request.json)

    @namespace.route('/service')
    class _Service(restplus.Resource):
        """Treadmill IPA Service"""
        @webutils.post_api(
            api,
            cors,
            req_model=service_model
        )
        def post(self):
            """Add Service to IPA"""
            return impl.service_add(flask.request.json)
