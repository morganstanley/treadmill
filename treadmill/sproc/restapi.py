"""Implementation of treadmill API server plugin."""


import click

from .. import rest
from .. import context
from .. import zkutils

from treadmill import cli
from treadmill.rest import api
from treadmill.rest import error_handlers  # noqa: F401


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('-p', '--port', required=True)
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill REST API')
    @click.option('-m', '--modules', help='API modules to load.',
                  required=True, type=cli.LIST)
    @click.option('-c', '--cors-origin', help='CORS origin REGEX',
                  required=True)
    def top(port, auth, title, modules, cors_origin):
        """Run Treadmill API server."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        api_paths = api.init(modules, title.replace('_', ' '), cors_origin)

        rest_server = rest.RestServer(port)
        rest_server.run(auth_type=auth, protect=api_paths)

    return top
