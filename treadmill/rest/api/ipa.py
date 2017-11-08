"""
Treadmill IPA REST api.
"""

import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


def handle_api_error(func):
    def wrapper(*args):
        try:
            return func(*args)
        except Exception as e:
            return flask.abort(400, {'message': e.message})
    return wrapper


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for ipa resource."""

    namespace = webutils.namespace(
        api, __name__, 'IPA REST operations'
    )

    service_req_model = {
        'hostname': fields.String(description='Hostname'),
        'domain': fields.String(description='Domain')
    }

    service_model = api.model(
        'service', service_req_model
    )

    @namespace.route('/host/<hostname>')
    @api.doc(params={'hostname': 'Hostname'})
    class _Host(restplus.Resource):
        """Treadmill IPA Host"""

        @webutils.post_api(
            api,
            cors,
        )
        def post(self, hostname):
            """Adds host to IPA."""
            return impl.add_host(hostname)

        @webutils.delete_api(
            api,
            cors,
        )
        def delete(self, hostname):
            """Deletes host from IPA."""
            return impl.delete_host(hostname)

    @namespace.route('/user/<username>')
    @api.doc(params={'username': 'Username'})
    class _User(restplus.Resource):
        """Treadmill IPA User"""

        @webutils.post_api(
            api,
            cors,
        )
        @handle_api_error
        def post(self, username):
            """Adds User to IPA."""
            impl.add_user(username)

        @webutils.delete_api(
            api,
            cors,
        )
        @handle_api_error
        def delete(self, username):
            """Deletes User from IPA."""
            return impl.delete_user(username)

    @namespace.route('/protocol/<protocol>/service/<service>')
    @api.doc(params={'service': 'Service',
                     'protocol': 'Protocol (ldap/zookeeper/etc)'})
    class _Service(restplus.Resource):
        """Treadmill IPA Service"""
        @webutils.post_api(
            api,
            cors,
            req_model=service_model
        )
        def post(self, protocol, service):
            """Add Service to IPA"""
            return impl.service_add(protocol, service, flask.request.json)
