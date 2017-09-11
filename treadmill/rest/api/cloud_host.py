"""
Treadmill Cloud Host REST api.
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
    """Configures REST handlers for cloud host resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cloud Host REST operations'
    )

    req_model = {
        'service': fields.String(description='Service Name'),
        'hostname': fields.String(description='Hostname'),
        'domain': fields.String(description='Domain')
    }

    ipa_service_model = api.model(
        'IPA', req_model
    )

    @namespace.route('/<hostname>')
    @api.doc(params={'hostname': 'hostname'})
    class _CloudHostResource(restplus.Resource):
        """Treadmill Cloud Host resource"""

        @webutils.post_api(api, cors, marshal=api.marshal_list_with)
        def post(self, hostname):
            """Adds host to IPA."""
            return impl.create(hostname)

        @webutils.delete_api(api, cors)
        def delete(self, hostname):
            """Deletes host from IPA."""
            return impl.delete(hostname)

    @namespace.route('/ipa/service')
    class _IPAServiceAdd(restplus.Resource):
        """Treadmill Service Allow Retrieve Keytab"""
        @webutils.post_api(
            api,
            cors,
            req_model=ipa_service_model
        )
        def post(self):
            """Whitelist host to Allowed hosts for service keytab retrieval."""
            return impl.ipa_service_add(flask.request.json)
