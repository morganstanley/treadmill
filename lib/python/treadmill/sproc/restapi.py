"""Implementation of treadmill API server plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import errno
import logging
import time
import socket as sock

import click

from treadmill import cli
from treadmill import context
from treadmill import rest
from treadmill import yamlwrapper as yaml
from treadmill import zkutils
from treadmill.rest import api
from treadmill.rest import error_handlers  # pylint: disable=W0611


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('-p', '--port', help='Port for TCP server')
    @click.option('-s', '--socket', help='Socket for UDS server')
    @click.option('-a', '--auth', help='Authentication plugin')
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill REST API')
    @click.option('-m', '--modules', help='API modules to load.',
                  required=True, type=cli.LIST)
    @click.option('--config', help='API configuration.',
                  multiple=True,
                  type=(str, click.File()))
    @click.option('-c', '--cors-origin', help='CORS origin REGEX',
                  required=True)
    @click.option('--workers', help='Number of workers', default=1)
    @click.option('--backlog', help='Maximum ', default=128)
    @click.option('-A', '--authz', help='Authoriztion argument',
                  required=False)
    def top(port, socket, auth, title, modules, config, cors_origin, workers,
            backlog, authz):
        """Run Treadmill API server."""
        context.GLOBAL.zk.add_listener(zkutils.exit_on_lost)

        api_modules = {module: None for module in modules}
        for module, cfg in config:
            if module not in api_modules:
                raise click.UsageError(
                    'Orphan config: %s, not in: %r' % (module, modules)
                )
            api_modules[module] = yaml.load(stream=cfg)
            cfg.close()

        api_paths = api.init(api_modules, title.replace('_', ' '), cors_origin,
                             authz)

        if port:
            rest_server = rest.TcpRestServer(port, auth_type=auth,
                                             protect=api_paths,
                                             workers=workers,
                                             backlog=backlog)
        # TODO: need to rename that - conflicts with import socket.
        elif socket:
            rest_server = rest.UdsRestServer(socket, auth_type=auth,
                                             workers=workers,
                                             backlog=backlog)
        else:
            click.echo('port or socket must be specified')
            sys.exit(1)

        try:
            rest_server.run()
        except sock.error as sock_err:
            _LOGGER.warning('Socker error: %s', sock_err)
            if sock_err.errno == errno.EADDRINUSE:
                # TODO: hack, but please keep it for now, otherwise on the
                #       setup several master processes run on same server
                #       lookup api (listen on port 8080) is in tight loop.
                time.sleep(5)

    return top
