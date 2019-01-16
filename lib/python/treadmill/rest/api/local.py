"""Local node REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import flask
import flask_restplus as restplus
from flask_restplus import inputs

from treadmill import webutils

_LOGGER = logging.getLogger(__name__)


def init(api, cors, impl):
    """Configures REST handlers for allocation resource."""

    app_ns = api.namespace(
        'local-app', description='Local app REST operations'
    )

    req_parser = api.parser()
    req_parser.add_argument('start',
                            default=0, help='The index (inclusive) of'
                            ' the first line from the log file to return.'
                            ' Index is zero based.',
                            location='args', required=False, type=int)
    req_parser.add_argument('limit',
                            help='The number of lines to return. '
                            '-1 (the default) means no limit ie. return all'
                            ' the lines in the file from "start".',
                            location='args', required=False, type=int,
                            default=-1)
    req_parser.add_argument('order',
                            choices=('asc', 'desc'), default='asc',
                            help='The order of the log lines to return. "asc":'
                            ' chronological, "desc": reverse chronological',
                            location='args', required=False, type=str)
    req_parser.add_argument('all',
                            default=False, help='Whether to return all the log'
                            'entries or just the latest ones',
                            location='args', required=False,
                            type=inputs.boolean)

    @app_ns.route('/', defaults={'app': None})
    @app_ns.route('/<app>')
    class _AppList(restplus.Resource):
        """Local app list resource."""

        @webutils.get_api(api, cors)
        def get(self, app):
            """Returns listof local instances."""
            return impl.list(
                state=flask.request.args.get('state'),
                app_name=app,
            )

    @app_ns.route('/<app>/<uniq>',)
    class _AppDetails(restplus.Resource):
        """Local app details resource."""

        @webutils.get_api(api, cors)
        def get(self, app, uniq):
            """Returns list of local instances."""
            return impl.get('/'.join([app, uniq]))

    @app_ns.route('/<app>/<uniq>/sys/<component>',)
    class _AppSystemLog(restplus.Resource):
        """Local app details resource."""

        def _to_rsrc_id(self, app, uniq, component):
            """Returns the log resource id based on the args."""
            return '/'.join([app, uniq, 'sys', component])

        @webutils.opt_gzip
        @webutils.raw_get_api(api, cors, parser=req_parser)
        def get(self, app, uniq, component):
            """Return content of system component log.."""
            kwargs = req_parser.parse_args()

            if kwargs.get('all'):
                return flask.Response(
                    impl.log.get_all(self._to_rsrc_id(app, uniq, component)),
                    mimetype='text/plain')

            del kwargs['all']  # 'all' is always in kwargs...
            return flask.Response(
                impl.log.get(self._to_rsrc_id(app, uniq, component), **kwargs),
                mimetype='text/plain')

    @app_ns.route('/<app>/<uniq>/service/<service>',)
    class _AppServiceLog(restplus.Resource):
        """Local app details resource."""

        def _to_rsrc_id(self, app, uniq, service):
            """Returns the log resource id based on the args."""
            return '/'.join([app, uniq, 'app', service])

        @webutils.opt_gzip
        @webutils.raw_get_api(api, cors, parser=req_parser)
        def get(self, app, uniq, service):
            """Return content of system component log.."""
            kwargs = req_parser.parse_args()

            if kwargs.get('all'):
                return flask.Response(
                    impl.log.get_all(self._to_rsrc_id(app, uniq, service)),
                    mimetype='text/plain')

            del kwargs['all']  # 'all' is always in kwargs...
            return flask.Response(
                impl.log.get(self._to_rsrc_id(app, uniq, service), **kwargs),
                mimetype='text/plain')

    archive_ns = api.namespace('archive',
                               description='Local archive REST operations')

    @archive_ns.route('/<app>/<uniq>/sys')
    class _SysArchiveAsAttachment(restplus.Resource):
        """Download sys archive as attachment."""

        @webutils.raw_get_api(api, cors)
        def get(self, app, uniq):
            """Return content of sys archived file.."""
            fname = impl.archive.get('/'.join([app, uniq, 'sys']))

            return flask.send_file(
                fname,
                as_attachment=True,
                attachment_filename=os.path.basename(fname)
            )

    @archive_ns.route('/<app>/<uniq>/app')
    class _AppArchiveAsAttachment(restplus.Resource):
        """Download app archive as attachment."""

        @webutils.raw_get_api(api, cors)
        def get(self, app, uniq):
            """Return content of app archived file.."""
            fname = impl.archive.get('/'.join([app, uniq, 'app']))

            return flask.send_file(
                fname,
                as_attachment=True,
                attachment_filename=os.path.basename(fname)
            )

    metrics_ns = api.namespace('metrics', description='Local metrics '
                               'REST operations')

    metrics_req_parser = api.parser()
    metrics_req_parser.add_argument(
        'timeframe',
        choices=('short', 'long'),
        default='short',
        help='Whether to query the metrics for shorter or longer timeframe.',
        location='args',
        required=False,
        type=str)

    @metrics_ns.route('/',)
    class _MetricsList(restplus.Resource):
        """Local metrics list resource."""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of locally available metrics."""
            return impl.list(flask.request.args.get('state'), inc_svc=True)

    @metrics_ns.route('/<app>/<uniq>')
    @metrics_ns.route('/<service>')
    class _Metrics(restplus.Resource):
        """Download metrics."""

        @webutils.raw_get_api(api, cors, parser=metrics_req_parser)
        def get(self, **id_parts):
            """
            Return metrics either as an attachment or as json.
            """
            args = metrics_req_parser.parse_args()
            if webutils.wants_json_resp(flask.request):
                return self._get(self._to_rsrc_id(**id_parts),
                                 args.get('timeframe'))
            else:
                return self._get_as_attach(self._to_rsrc_id(**id_parts),
                                           args.get('timeframe'))

        def _to_rsrc_id(self, **id_parts):
            """
            Return the metrics resource id based on the keyword args.
            """
            try:
                rsrc_id = '/'.join([id_parts['app'], id_parts['uniq']])
            except KeyError:
                rsrc_id = id_parts['service']

            return rsrc_id

        def _get(self, rsrc_id, timeframe):
            """Return the metrics file as json."""
            return flask.Response(impl.metrics.get(rsrc_id, timeframe,
                                                   as_json=True),
                                  mimetype='application/json')

        def _get_as_attach(self, rsrc_id, timeframe):
            """Return the metrics file as attachment."""
            return flask.send_file(
                impl.metrics.get(rsrc_id, timeframe),
                as_attachment=True,
                mimetype='application/octet-stream',
                attachment_filename=os.path.basename(
                    impl.metrics.file_path(rsrc_id)
                )
            )
