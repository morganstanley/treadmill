"""Warpgate client CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import cli
from treadmill.warpgate import client


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--policy-servers', type=cli.LIST,
                  required=True,
                  help='Warpgate policy servers')
    @click.option('--service-principal', type=str,
                  default='host',
                  help='Warpgate service principal.')
    @click.option('--policy', type=str, required=True,
                  envvar='WARPGATE_POLICY',
                  help='Warpget policy to use')
    @click.option('--tun-dev', type=str, required=True,
                  help='Device to use when establishing tunnels.')
    @click.option('--tun-addr', type=str, required=False,
                  help='Local IP address to use when establishing tunnels.')
    def warpgate(policy_servers, service_principal, policy, tun_dev, tun_addr):
        """Run warpgate connection manager.
        """
        _LOGGER.info(
            'Launch client => %s, tunnel: %s[%s], policy: %s, principal: %s',
            policy_servers,
            tun_dev, tun_addr,
            policy,
            service_principal,
        )
        # Never exits
        client.run_client(
            policy_servers, service_principal, policy,
            tun_dev, tun_addr
        )

    return warpgate
