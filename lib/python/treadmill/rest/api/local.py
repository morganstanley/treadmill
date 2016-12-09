"""
Local node REST api.
"""
from __future__ import absolute_import

import os
import httplib

# pylint: disable=E0611,F0401
import flask
import flask.ext.restplus as restplus
from flask import request

from treadmill import webutils


def _archive_type():
    """Get archive type from query string."""
    archive_type = request.args.get('type')
    if not archive_type:
        archive_type = 'app'

    if archive_type not in ['app', 'sys']:
        # TODO: need to raise validation error exception.
        raise Exception('Invalid archive type.')

    return archive_type


# pylint: disable=W0232,R0912
def init(api, cors, impl):
    """Configures REST handlers for allocation resource."""

    namespace = api.namespace('local',
                              description='Local server REST operations')

    @namespace.route('/running',)
    class _RunningList(restplus.Resource):
        """Treadmill Allocation resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list running containers."""
            return impl.running.list()

    @namespace.route('/running/<instance>',)
    class _RunningDetails(restplus.Resource):
        """Treadmill Allocation resource"""

        @webutils.get_api(api, cors)
        def get(self, instance):
            """Returns list running containers."""
            return impl.running.get(instance)

    @namespace.route('/running/<instance>/sys/<component>')
    class _RunningSystemLog(restplus.Resource):
        """System log stream."""

        def get(self, instance, component):
            """Return content of archived file.."""
            mimetype = 'text/plain'
            return flask.Response(
                impl.running.lines(instance, 'sys', component),
                mimetype=mimetype
            )

    @namespace.route('/running/<instance>/service/<component>')
    class _RunningServiceLog(restplus.Resource):
        """System log stream."""

        def get(self, instance, component):
            """Return content of archived file.."""
            mimetype = 'text/plain'
            return flask.Response(
                impl.running.lines(instance, 'services', component),
                mimetype=mimetype
            )

    @namespace.route('/archive/<instance>',)
    class _ArchiveList(restplus.Resource):
        """Archive resource."""

        @webutils.get_api(api, cors)
        def get(self, instance):
            """Returns list of archives."""
            archive_type = _archive_type()
            return impl.archive.list(archive_type, instance)

    @namespace.route('/archive/<instance>/<idx>',)
    class _ArchiveDetails(restplus.Resource):
        """Archive resource."""

        @webutils.get_api(api, cors)
        def get(self, instance, idx):
            """Returns archive details."""
            idx = int(idx)
            archive_type = _archive_type()
            return impl.archive.get(archive_type, instance, idx)

    @namespace.route('/archive/<instance>/<idx>/file/<path:path>')
    class _ArchiveFile(restplus.Resource):
        """Archive resource."""

        def get(self, instance, idx, path):
            """Return content of archived file.."""
            idx = int(idx)
            archive_type = _archive_type()
            mimetype = 'text/plain'

            return flask.Response(
                impl.archive.lines(archive_type, instance, idx, path),
                mimetype=mimetype
            )

    @namespace.route('/archive/<instance>/<idx>/fetch')
    class _ArchiveAsAttachment(restplus.Resource):
        """Download archive as attachment."""

        def get(self, instance, idx):
            """Return content of archived file.."""
            idx = int(idx)
            archive_type = _archive_type()
            fname = impl.archive.path(archive_type, instance, idx)

            if not os.path.exists(fname):
                return 'Not found.', httplib.NOT_FOUND

            return flask.send_file(
                fname,
                as_attachment=True,
                attachment_filename=os.path.basename(fname)
            )
