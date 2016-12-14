"""Node info sproc module."""
from __future__ import absolute_import

import logging
import httplib
import socket

import click
import flask
import kazoo

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

_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcd')


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
    def server(register, port, auth, modules, title, cors_origin):
        """Runs nodeinfo server."""
        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        hostname = sysinfo.hostname()
        hostport = '%s:%s' % (hostname, port)

        if register:
            zkclient = context.GLOBAL.zk.conn
            zkclient.add_listener(zkutils.exit_on_lost)

            appname = 'root.%s#0000000000' % hostname
            path = z.path.endpoint(appname, 'tcp', 'nodeinfo')
            _LOGGER.info('register endpoint: %s %s', path, hostport)
            zkutils.put(zkclient, path, hostport, acl=[_SERVERS_ACL])

        _LOGGER.info('Starting nodeinfo server on port: %s', port)

        utils.drop_privileges()

        api_paths = []
        if modules:
            api_paths = api.init(modules, title.replace('_', ' '), cors_origin)

        rest_server = rest.RestServer(port)
        rest_server.run(auth_type=auth, protect=api_paths)

    del redirector
    del server

    return nodeinfo_grp
