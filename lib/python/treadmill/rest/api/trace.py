"""Treadmill State REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_restplus as restplus
from flask_restplus import fields

from treadmill import exc
from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for state resource."""
    namespace = webutils.namespace(
        api, __name__, 'Trace REST operations'
    )

    model = {
        'name': fields.String(description='Application name'),
        'instances': fields.List(
            fields.String(description='Instance IDs')
        ),
    }
    trace_model = api.model(
        'Trace', model
    )

    @namespace.route('/<app_name>')
    @api.doc(params={'app_name': 'Application name'})
    class _TraceAppResource(restplus.Resource):
        """Treadmill application trace information resource.
        """

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=trace_model)
        def get(self, app_name):
            """Return trace information of a Treadmill application.
            """
            trace_info = impl.get(app_name)
            if trace_info is None:
                raise exc.NotFoundError(
                    'No trace information available for {}'.format(app_name)
                )
            return trace_info
