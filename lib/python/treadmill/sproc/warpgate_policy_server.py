"""Warpgate policy server CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket

import click

from treadmill import cli
from treadmill.warpgate import policy_server


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--port', type=int, help='Port to listen.', default=0)
    @click.option('--tun-dev', type=str, required=True,
                  help='Device to use when establishing tunnels.')
    @click.option('--tun-addr', type=str, required=False,
                  help='Local IP address to use when establishing tunnels.')
    @click.option('--tun-cidrs', type=cli.LIST, required=True,
                  help='CIDRs block assigned to the tunnels.')
    @click.option('--policies-dir', type=str, required=True,
                  help='Directory where to look for policies')
    @click.option('--state-dir', type=str, required=False,
                  default='/var/run/warpgate',
                  help='Directory where running state is kept')
    def warpgate_policy_server(port, tun_dev, tun_addr, tun_cidrs,
                               policies_dir, state_dir):
        """Run warpgate policy server."""

        myhostname = socket.getfqdn()
        policy_server.run_server(
            admin_address=myhostname,
            admin_port=port,
            tun_devname=tun_dev,
            tun_address=(
                tun_addr if tun_addr else socket.gethostbyname(myhostname)
            ),
            tun_cidrs=tun_cidrs,
            policies_dir=policies_dir,
            state_dir=state_dir
        )

    return warpgate_policy_server
