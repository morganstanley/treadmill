"""Implementation of treadmill API server plugin."""
from __future__ import absolute_import

import importlib
import logging

import click

from .. import rest
from .. import context
from .. import zkutils
# TODO: consider refactoring error_handlers so that exceptions are
#                configured in function, not on import.
from treadmill.rest import error_handlers  # pylint: disable=W0611
from treadmill import cli


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('-p', '--port', required=True)
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-v', '--versions', help='List of API versions.',
                  required=True, type=cli.LIST)
    @click.option('-m', '--modules', help='API modules to load.',
                  required=True, type=cli.LIST)
    def top(port, auth, versions, modules):
        """Run Treadmill API server."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)
        api_paths = []
        for version in versions:
            module_name = 'treadmill.rest.' + version
            logging.info('import %s', module_name)
            mod = importlib.import_module(module_name)
            api_paths.extend(mod.init(modules))

        rest_server = rest.RestServer(port)
        rest_server.run(auth_type=auth, protect=api_paths)

    return top
