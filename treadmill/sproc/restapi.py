"""Implementation of treadmill API server plugin."""


import sys

import click

from treadmill import context
from treadmill import rest
from treadmill import zkutils

from treadmill import cli
from treadmill.rest import api
from treadmill.rest import error_handlers  # noqa: F401


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
    @click.option('--workers', help='Number of workers',
                  default=5)
    @click.option('-A', '--authz', help='Authoriztion argument',
                  required=False)
    def top(port, socket, auth, title, modules, cors_origin, workers, authz):
        """Run Treadmill API server."""
        context.GLOBAL.zk.add_listener(zkutils.exit_on_lost)

        api_paths = api.init(modules, title.replace('_', ' '), cors_origin,
                             authz)

        if port:
            rest_server = rest.TcpRestServer(port, auth_type=auth,
                                             protect=api_paths,
                                             workers=workers)
        elif socket:
            rest_server = rest.UdsRestServer(socket)
        else:
            click.echo('port or socket must be specified')
            sys.exit(1)

        rest_server.run()

    return top
