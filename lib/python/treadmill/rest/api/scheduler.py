"""Scheduler reports REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for scheduler resource."""
    namespace = webutils.namespace(
        api, __name__, 'Scheduler reports REST operations'
    )

    report_resource_resp_model = api.model('Report', {
        'columns': fields.List(
            fields.String(description='Column name')
        ),
        'data': fields.List(fields.List(fields.Raw()))
    })

    arg_parser = api.parser()
    arg_parser.add_argument(
        'match', help='Glob pattern to match name or instance',
        location='args',
        required=False,
        default=None,
    )
    arg_parser.add_argument(
        'partition', help='Glob pattern to match partition',
        location='args',
        required=False,
        default=None,
    )

    def fetch_report(report_type, match=None, partition=None):
        """Fetch the report from the impl and return it as json."""
        status = 200
        try:
            report = impl.get(report_type, match=match, partition=partition)
            output = report.to_dict(orient='split')
            del output['index']  # just a list of 0 to n, not useful
        except KeyError:
            output = {
                'message': 'No such scheduler report: {}'.format(report_type),
                'report_type': report_type
            }
            status = 404

        return flask.current_app.response_class(
            # Use the json_encoder configured in the Flask app
            response=flask.json.dumps(output),
            status=status,
            mimetype='application/json'
        )

    @namespace.route('/servers')
    class _ServersResource(restplus.Resource):
        """Servers report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=arg_parser,
            json_resp=False  # Bypass webutils.as_json
        )
        def get(self):
            """Return the servers report."""
            args = arg_parser.parse_args()
            return fetch_report('servers', **args)

    @namespace.route('/allocations')
    class _AllocsResource(restplus.Resource):
        """Allocations report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=arg_parser,
            json_resp=False  # Bypass webutils.as_json
        )
        def get(self):
            """Return the allocations report."""
            args = arg_parser.parse_args()
            return fetch_report('allocations', **args)

    @namespace.route('/apps')
    class _AppsResource(restplus.Resource):
        """Apps report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=arg_parser,
            json_resp=False  # Bypass webutils.as_json
        )
        def get(self):
            """Return the apps report."""
            args = arg_parser.parse_args()
            return fetch_report('apps', **args)
