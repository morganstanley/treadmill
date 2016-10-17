"""Node info sproc module."""
from __future__ import absolute_import

import glob
import os
import logging
import httplib
import socket
import tarfile

import click
import flask
import kazoo

from treadmill import appmgr
from treadmill import cli
from treadmill import context
from treadmill import sysinfo
from treadmill import utils
from treadmill import zkutils
from treadmill import zknamespace as z
from treadmill import rest
from treadmill.rest import api
from treadmill.rest import error_handlers  # pylint: disable=W0611


_LOGGER = logging.getLogger(__name__)


def _send_file(filename):
    """Return system archive for the given app."""
    if not os.path.exists(filename):
        return 'Not found.', httplib.NOT_FOUND

    return flask.send_file(
        filename,
        as_attachment=True,
        attachment_filename=os.path.basename(filename)
    )


def _stream_archived_file(archive_file, filename, mimetype=None):
    """Stream file from the archive."""
    _LOGGER.info('Stream archive file: %s, %s', archive_file, filename)

    def _yield_lines(archive_file, filename):
        with tarfile.open(archive_file) as archive:
            member = archive.extractfile(filename)
            for line in member:
                yield line

    if not mimetype:
        mimetype = 'text/plain'

    return flask.Response(
        _yield_lines(archive_file, filename),
        mimetype=mimetype
    )


def _stream_file(filename, mimetype=None):
    """Stream file."""
    _LOGGER.info('Stream file: %s', filename)

    def _yield_lines(filename):
        """Yield lines from the file."""
        with open(filename) as f:
            for line in f:
                yield line

    if not mimetype:
        mimetype = 'text/plain'
    return flask.Response(
        _yield_lines(filename),
        mimetype=mimetype
    )


def _view_log_handler(tm_env, appname, instance, logtype, component):
    """View system component log given app instance."""
    _LOGGER.info('Log handler: %s, %s, %s', appname, logtype, component)

    app_running_dir = os.path.join(
        tm_env.running_dir, '%s#%s' % (appname, instance)
    )
    if os.path.exists(app_running_dir):
        return _stream_file(
            os.path.join(app_running_dir, logtype, component, 'log', 'current')
        )
    else:
        archive_glob = os.path.join(
            tm_env.archives_dir,
            '%s-%s-*%s.tar.gz' % (appname, instance, logtype)
        )
        archives = glob.glob(archive_glob)
        if archives:
            # TODO(andreik) - this need to be fixes, order archives
            # by ctime.
            return _stream_archived_file(
                archives[0],
                os.path.join(logtype, component, 'log', 'current')
            )
    # Default - not found.
    if not archives:
        return 'Not found.', httplib.NOT_FOUND


def init():
    """Top level command handler."""

    @click.group(name='nodeinfo')
    def nodeinfo_grp():
        """Manages local node info server and redirector."""
        pass

    @nodeinfo_grp.command()
    @click.option('-p', '--port', required=False, default=8000)
    def redirector(port):
        """Runs local nodeinfo redirector."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        app = flask.Flask(__name__)

        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_lost)

        @app.route('/<hostname>/<path:path>')
        def _redirect(hostname, path):
            """Redirect to host specific handler."""
            _LOGGER.info('Redirect: %s %s', hostname, path)
            try:
                hostport, _metadata = zkclient.get(z.path.nodeinfo(hostname))
                _LOGGER.info('Found: %s - %s', hostname, hostport)
                return flask.redirect(
                    'http://%s/%s' % (hostport, path),
                    code=httplib.FOUND
                )
            except kazoo.client.NoNodeError:
                return 'Host not found.', httplib.NOT_FOUND

        app.run(host='0.0.0.0', port=port)

    @nodeinfo_grp.command()
    @click.option('-r', '--register', required=False, default=False,
                  is_flag=True, help='Register as /nodeinfo in Zookeeper.')
    @click.option('-p', '--port', required=False, default=0)
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-m', '--modules', help='API modules to load.',
                  required=False, type=cli.LIST)
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill Nodeinfo REST API')
    @click.option('-c', '--cors-origin', help='CORS origin REGEX')
    @click.argument('approot', 'Treadmill install root.',
                    envvar='TREADMILL_APPROOT')
    def server(register, port, auth, modules, title, cors_origin, approot):
        """Runs nodeinfo server."""
        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        tm_env = appmgr.AppEnvironment(approot)

        hostname = sysinfo.hostname()
        hostport = '%s:%s' % (hostname, port)

        if register:
            zkclient = context.GLOBAL.zk.conn
            zkclient.add_listener(zkutils.exit_on_lost)
            nodeinfo_path = z.path.nodeinfo(hostname)
            _LOGGER.info('Registering: %s %s', nodeinfo_path, hostport)

            zkutils.ensure_deleted(zkclient, nodeinfo_path)
            zkutils.put(zkclient, nodeinfo_path, hostport)

        _LOGGER.info('Starting nodeinfo server on port: %s', port)

        utils.drop_privileges()

        api_paths = []
        if modules:
            api_paths = api.init(modules, title.replace('_', ' '), cors_origin)

        @rest.FLASK_APP.route('/fetch/archive/sys/<appname>')
        def _fetch_sys_archive(appname):
            """Return system archive for the given app."""
            return _send_file(
                os.path.join(tm_env.archives_dir, '%s.sys.tar.gz' % (appname))
            )

        @rest.FLASK_APP.route('/fetch/archive/app/<appname>')
        def _fetch_app_archive(appname):
            """Return app archive for the given app."""
            # TODO(andreik): need to add authorization.
            return _send_file(
                os.path.join(tm_env.archives_dir, '%s.app.tar.gz' % (appname))
            )

        @rest.FLASK_APP.route('/view/archive/sys/<appname>/<path:path>')
        def _view_sys_archive(appname, path):
            """Return system archive for the given app."""
            archive_file = os.path.join(tm_env.archives_dir,
                                        '%s.sys.tar.gz' % (appname))

            return _stream_archived_file(archive_file, path)

        @rest.FLASK_APP.route('/view/archive/app/<appname>/<path:path>')
        def _view_app_archive(appname, path):
            """Return system archive for the given app."""
            archive_file = os.path.join(tm_env.archives_dir,
                                        '%s.app.tar.gz' % (appname))

            return _stream_archived_file(archive_file, path)

        @rest.FLASK_APP.route('/log/<appname>/<instance>/system/<component>')
        def _view_system_log(appname, instance, component):
            """View system component log given app instance."""
            _LOGGER.info('System log: %s#%s: %s', appname, instance, component)
            return _view_log_handler(
                tm_env, appname, instance, 'sys', component)

        @rest.FLASK_APP.route('/log/<appname>/<instance>/service/<service>')
        def _view_service_log(appname, instance, service):
            """View system component log given app instance."""
            _LOGGER.info('Service log: %s#%s: %s', appname, instance, service)
            return _view_log_handler(
                tm_env, appname, instance, 'services', service)

        rest_server = rest.RestServer(port)
        api_paths.extend(['/view', '/fetch'])
        rest_server.run(auth_type=auth, protect=api_paths)

    del redirector
    del server

    return nodeinfo_grp
