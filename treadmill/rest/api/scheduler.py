"""Scheduler reports REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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

    match_parser = api.parser()
    match_parser.add_argument(
        'match',
        help='glob to match name or instance',
        location='args',
        required=False
    )

    def fetch_report(report_type, match=None):
        """Fetch the report from the impl and return it as json."""
        try:
            report = impl.get(report_type, match=match)
            output = report.to_dict(orient='split')
            del output['index']  # just a list of 0 to n, not useful
            return output
        except KeyError:
            return {
                'message': 'No such scheduler report: {}'.format(report_type),
                'report_type': report_type
            }, 404

    @namespace.route('/servers')
    class _ServersResource(restplus.Resource):
        """Servers report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=match_parser
        )
        def get(self):
            """Return the servers report."""
            args = match_parser.parse_args()
            return fetch_report('servers', match=args.get('match'))

    @namespace.route('/allocations')
    class _AllocsResource(restplus.Resource):
        """Allocations report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=match_parser
        )
        def get(self):
            """Return the allocations report."""
            args = match_parser.parse_args()
            return fetch_report('allocations', match=args.get('match'))

    @namespace.route('/apps')
    class _AppsResource(restplus.Resource):
        """Apps report resource."""
        @webutils.get_api(
            api,
            cors,
            resp_model=report_resource_resp_model,
            parser=match_parser
        )
        def get(self):
            """Return the apps report."""
            args = match_parser.parse_args()
            return fetch_report('apps', match=args.get('match'))
