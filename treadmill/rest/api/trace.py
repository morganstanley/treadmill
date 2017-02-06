"""
Treadmill State REST api.
"""


import http.client

import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for state resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'Trace REST operations'
    )

    trace_info_model = {
        'name': fields.String(description='Application name'),
        'instances': fields.List(
            fields.String(description='Instance IDs')
        ),
    }
    response_model = api.model(
        'RespState', trace_info_model
    )

    @namespace.route('/<app_name>')
    @api.doc(params={'app_name': 'Application name'})
    class _TraceAppResource(restplus.Resource):
        """Treadmill application trace information resource.
        """

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, app_name):
            """Return trace information of a Treadmill application.
            """
            trace_info = impl.get(app_name)
            if trace_info is None:
                api.abort(http.client.NOT_FOUND,
                          'No trace information available for %s' % app_name)
            return trace_info
