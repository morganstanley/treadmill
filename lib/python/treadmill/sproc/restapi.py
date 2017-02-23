"""Implementation of treadmill API server plugin."""
from __future__ import absolute_import

import sys

import click

from .. import rest
from .. import context
from .. import zkutils

from treadmill import cli
from treadmill.rest import api
from treadmill.rest import error_handlers  # pylint: disable=W0611


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('-p', '--port', help='Port for TCP server')
    @click.option('-s', '--socket', help='Socket for UDS server')
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill REST API')
    @click.option('-m', '--modules', help='API modules to load.',
                  required=True, type=cli.LIST)
    @click.option('-c', '--cors-origin', help='CORS origin REGEX',
                  required=True)
    def top(port, socket, auth, title, modules, cors_origin):
        """Run Treadmill API server."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        api_paths = api.init(modules, title.replace('_', ' '), cors_origin)

        if port:
            rest_server = rest.TcpRestServer(port, auth_type=auth,
                                             protect=api_paths)
        elif socket:
            rest_server = rest.UdsRestServer(socket)
        else:
            click.echo('port or socket must be specified')
            sys.exit(1)

        rest_server.run()

    return top
