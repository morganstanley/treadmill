"""
Local node REST api.
"""


import os
import http.client

# pylint: disable=E0611,F0401
import flask
import flask_restplus as restplus

from treadmill import webutils


# pylint: disable=W0232,R0912
def init(api, cors, impl):
    """Configures REST handlers for allocation resource."""

    app_ns = api.namespace('app', description='Local app REST operations')

    @app_ns.route('/',)
    class _AppList(restplus.Resource):
        """Local app list resource."""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of local instances."""
            return impl.list(flask.request.args.get('state'))

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

        @webutils.raw_get_api(api, cors)
        def get(self, app, uniq, component):
            """Return content of system component log.."""
            mimetype = 'text/plain'
            return flask.Response(
                impl.log.get('/'.join([app, uniq, 'sys', component])),
                mimetype=mimetype
            )

    @app_ns.route('/<app>/<uniq>/service/<service>',)
    class _AppServiceLog(restplus.Resource):
        """Local app details resource."""

        @webutils.raw_get_api(api, cors)
        def get(self, app, uniq, service):
            """Return content of system component log.."""
            mimetype = 'text/plain'
            return flask.Response(
                impl.log.get('/'.join([app, uniq, 'app', service])),
                mimetype=mimetype
            )

    archive_ns = api.namespace('archive',
                               description='Local archive REST operations')

    @archive_ns.route('/<app>/<uniq>/sys')
    class _SysArchiveAsAttachment(restplus.Resource):
        """Download sys archive as attachment."""

        @webutils.raw_get_api(api, cors)
        def get(self, app, uniq):
            """Return content of sys archived file.."""
            fname = impl.archive.get('/'.join([app, uniq, 'sys']))
            if not os.path.exists(fname):
                return 'Not found.', http.client.NOT_FOUND

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
            if not os.path.exists(fname):
                return 'Not found.', http.client.NOT_FOUND

            return flask.send_file(
                fname,
                as_attachment=True,
                attachment_filename=os.path.basename(fname)
            )
