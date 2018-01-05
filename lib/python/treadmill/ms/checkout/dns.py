"""DNS replication check.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import logging

from treadmill import admin
from treadmill import context
from treadmill import dnsutils
from treadmill import checkout as chk

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import dyndnsclient


_LOGGER = logging.getLogger(__name__)


def test():
    """Create DNS test class."""
    cell = context.GLOBAL.cell
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    admin_dns = admin.DNS(context.GLOBAL.ldap.conn)

    cell_obj = admin_cell.get(cell)
    dns_objs = admin_dns.list({'location': cell_obj['location']})

    if not dns_objs:
        # cell location is <region>.<campus>, if we can't find a dns with
        # that location try with just <region>
        region = cell_obj['location'].split('.')[0]
        dns_objs = admin_dns.list({'location': region})

    if not dns_objs:
        raise Exception(
            'No DNS entries for this cell location %s' % cell_obj['location']
        )

    class DnsTest(unittest.TestCase):
        """DNS checkout."""

    for dns in dns_objs:
        dyndns = dyndnsclient.DyndnsClient(dns['rest-server'])
        zones = dyndns.get('bind/zone')
        servers = dns['server']

        for zone in zones:

            @chk.T(DnsTest, zone=zone, servers=servers)
            def _test_replication(self, zone, servers):
                """Check replication for zone: {zone}."""
                serials = set()

                for server in servers:
                    host, port = server.split(':')
                    answer = dnsutils.soa(zone, ([host], int(port)))
                    for rdata in answer:
                        print(host, 'has serial', rdata.serial)
                        serials.add(rdata.serial)

                self.assertEqual(len(serials), 1,
                                 'Not all SOA serials are the same.')

    return DnsTest
