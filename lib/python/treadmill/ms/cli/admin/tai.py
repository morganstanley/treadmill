"""Search TAI dumps for server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools

import click
import six

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import taidw


def init():
    """Top level command handler."""

    @click.command()
    @click.option('-e', '--env', help='Environment to list',
                  required=True)
    @click.option('-d', '--dump_ip', help='Dump every IP',
                  is_flag=True, default=False)
    def search(env, dump_ip):
        """Search TAI dumps for server."""

        prod_server_ips = taidw.server_ip_gen(
            taidw.env_entry_gen(
                taidw.dump_entry_gen(taidw.SERVER_DAT),
                env=env
            )
        )
        prod_service_ips = taidw.service_ip_gen(
            taidw.env_entry_gen(
                taidw.dump_entry_gen(taidw.SERVICE_DAT),
                env=env
            )
        )

        if env in taidw.VIPS_TXT:
            vip_ips = taidw.vip_ip_gen(taidw.VIPS_TXT[env])
        else:
            vip_ips = []

        prod_ips = itertools.chain(prod_server_ips, prod_service_ips, vip_ips)
        count = 0

        res = [ip for _idx, ip in zip(six.moves.range(200), prod_ips)]
        while res:
            count += len(res)
            if dump_ip:
                for ip in res:
                    print(ip)
            res = [ip for _idx, ip in zip(six.moves.range(200), prod_ips)]

    return search
