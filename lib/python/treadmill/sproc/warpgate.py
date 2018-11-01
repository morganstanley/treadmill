"""Warpgate policy server.

Listens to client requests, and replies back with the policy to
establish GRE tunnel inside the container.

Only host/ principals are trusted (root credentials).
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
import socket

import click

from treadmill import cli
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.gssapiprotocol import jsonclient


_LOGGER = logging.getLogger(__name__)


def _policy_servers(zkclient):
    """Get warpgate policy servers for the cell."""
    endpoints = zkutils.with_retry(
        zkclient.get_children, z.path.warpgate()
    )
    random.shuffle(endpoints)
    return endpoints


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--policy-servers', type=cli.LIST,
                  help='Warpgate policy servers')
    @click.option('--service-principal',
                  help='Warpgate service principal.')
    def warpgate(policy_servers, service_principal):
        """Run warpgate container manager."""

        if not policy_servers:
            policy_servers = _policy_servers(context.GLOBAL.zk.conn)

        if not service_principal:
            service_principal = 'host'

        # Establish connection to the policy server and keep it open.
        #
        # Disconnecting from the policy server will retry with the next in the
        # list. If all fail, exit.
        #
        # In case policy servers change in Zookeeper, process will restart by
        # the supervisor, and re-evaluate.
        for hostport in policy_servers:
            _LOGGER.info('Connecting to %s', hostport)
            host, port = hostport.split(':')

            client = jsonclient.GSSAPIJsonClient(
                host, int(port), '{}@{}'.format(service_principal, host)
            )
            try:
                if not client.connect():
                    continue
                client.write_json({})
                policy = client.read_json()
                _LOGGER.info('Policy: %r', policy)
                # This will block, holding the connection.
                wait_for_reply = client.read()
                if wait_for_reply is None:
                    continue
            except socket.error as sock_err:
                _LOGGER.warning('Exception connecting to %s:%s - %s',
                                host, port, sock_err)

    return warpgate
