"""Warpgate policy server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random

import click
from twisted.internet import protocol
from twisted.internet import reactor

from treadmill import context
from treadmill import sysinfo
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.gssapiprotocol import jsonserver


_LOGGER = logging.getLogger(__name__)


class WarpgatePolicyServer(jsonserver.GSSAPIJsonServer):
    """Warpgate policy server."""

    def on_request(self, request):
        """Process policy request."""
        # TODO: this is stub, request is unused.
        del request

        peer = self.peer()
        # Stub response.
        return {
            'warpgate': {
                'peer': peer,
                'session': random.randint(0, 1024)
            }
        }


class WarpgatePolicyServerFactory(protocol.Factory):
    """Warpgate policy server factory."""

    def buildProtocol(self, addr):  # pylint: disable=C0103
        return WarpgatePolicyServer()


def _register_endpoint(zkclient, port):
    """Register policy server endpoint in Zookeeper."""
    hostname = sysinfo.hostname()
    zkclient.ensure_path(z.path.warpgate())

    node_path = z.path.warpgate('%s:%s' % (hostname, port))
    _LOGGER.info('registering locker: %s', node_path)
    if zkclient.exists(node_path):
        _LOGGER.info('removing previous node %s', node_path)
        zkutils.ensure_deleted(zkclient, node_path)

    zkutils.put(zkclient, node_path, {}, acl=None, ephemeral=True)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--port', type=int, help='Port to listen.', default=0)
    @click.option('--register', is_flag=True, default=False,
                  help='Register warpgate endpoint in Zookeeper.')
    def warpgate_policy_server(port, register):
        """Run warpgate policy server."""

        real_port = reactor.listenTCP(
            port, WarpgatePolicyServerFactory()).getHost().port
        _LOGGER.info('Starting warpgate policy server on port: %s', real_port)

        if register:
            _register_endpoint(context.GLOBAL.zk.conn, real_port)

        reactor.run()

    return warpgate_policy_server
