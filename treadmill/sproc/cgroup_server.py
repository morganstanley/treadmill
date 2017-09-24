"""Start Treadmill cgroups server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import errno
import sys
import time
import socket as sock

import click

from treadmill import rest
from treadmill.rest import api
from treadmill.metrics import cgroup_api

_LOGGER = logging.getLogger(__name__)


def init():
    """App main."""

    # pylint: disable=W0612
    @click.command()
    @click.option('-p', '--port', help='Port for TCP server')
    @click.option('-s', '--socket', help='Socket for UDS server')
    @click.option('-a', '--auth', type=click.Choice(['spnego']))
    @click.option('-t', '--title', help='API Doc Title',
                  default='Treadmill REST API')
    @click.option('-c', '--cors-origin', help='CORS origin REGEX',
                  required=True)
    @click.option('--workers', help='Number of workers',
                  default=5)
    @click.option('--interval', help='interval to refresh cgroups',
                  default=60)
    def server(port, socket, auth, title, cors_origin, workers, interval):
        """Create pge server to provide authorize service."""
        (base_api, cors) = api.base_api(title, cors_origin)
        endpoint = cgroup_api.init(base_api, cors, interval=interval)
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        if port:
            rest_server = rest.TcpRestServer(
                port, auth_type=auth,
                protect=[endpoint],
                workers=workers
            )
        # TODO: need to rename that - conflicts with import socket.
        elif socket:
            rest_server = rest.UdsRestServer(socket)
        else:
            click.echo('port or socket must be specified')
            sys.exit(1)
        try:
            rest_server.run()
        except sock.error as sock_err:
            print(sock_err)
            if sock_err.errno == errno.EADDRINUSE:
                # TODO: hack, but please keep it for now, otherwise on the
                #       setup several master processes run on same server
                #       lookup api (listen on port 8080) is in tight loop.
                time.sleep(5)

    return server
