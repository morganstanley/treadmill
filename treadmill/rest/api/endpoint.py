"""
Treadmill Endpoint REST api.
"""


import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for endpoint resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'Endpoint state REST operations'
    )

    endpoint_model = {
        'endpoint': fields.String(description='Endpoint name'),
        'name': fields.String(description='Application name'),
        'port': fields.Integer(description='Endpoint port'),
        'proto': fields.String(description='Application endpoint protocol'),
        'host': fields.String(description='Endpoint host'),
    }

    response_model = api.model(
        'RespEndpoint', endpoint_model
    )

    @namespace.route(
        '/<pattern>',
    )
    @api.doc(params={'pattern': 'Application pattern'})
    class _EndpointList(restplus.Resource):
        """Treadmill Endpoint resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self, pattern):
            """Return all endpoints"""
            ret = impl.list(pattern, None, None)
            print(ret)
            return ret

    @namespace.route('/<pattern>/<proto>/<endpoint>')
    @api.doc(params={
        'pattern': 'Application pattern',
        'proto': 'Application endpoint protocol',
        'endpoint': 'Application endpoint name',
    })
    class _EndpointResource(restplus.Resource):
        """Treadmill Endpoint resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self, pattern, proto, endpoint):
            """Return Treadmill app endpoint state"""
            ret = impl.list(pattern, proto, endpoint)
            print(ret)
            return ret
