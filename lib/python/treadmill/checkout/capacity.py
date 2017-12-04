"""Verifies system apps are running.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import admin
from treadmill import context
from treadmill import checkout as chk
from treadmill import presence
from treadmill import zknamespace as z


def test():
    """Create sysapps test class."""
    admin_srv = admin.Server(context.GLOBAL.ldap.conn)
    cell = context.GLOBAL.cell

    ldap_servers = [item['_id'] for item in admin_srv.list({'cell': cell})]

    zkclient = context.GLOBAL.zk.conn

    configured_servers = zkclient.get_children(z.SERVERS)
    up_servers = [presence.server_hostname(node)
                  for node in zkclient.get_children(z.SERVER_PRESENCE)]
    blackedout_servers = zkclient.get_children(z.BLACKEDOUT_SERVERS)
    rebooted_servers = zkclient.get_children(z.REBOOTS)

    class LdapSyncTest(unittest.TestCase):
        """Checks LDAP to Zookeeper server sync."""

    for server in ldap_servers:
        @chk.T(LdapSyncTest,
               server=server, configured_servers=configured_servers)
        def _test_server_configured(self, server, configured_servers):
            """Check if server is synced between LDAP and Zk: {server}."""
            self.assertIn(server, configured_servers)

    class ServerTest(unittest.TestCase):
        """Checks server(s) are up and alive."""

    expected_up = (
        set(configured_servers) -
        set(blackedout_servers) -
        set(rebooted_servers)
    )

    for server in expected_up:
        @chk.T(ServerTest, server=server, up_servers=up_servers)
        def _test_server_up(self, server, up_servers):
            """Check if server is up: {server}."""
            self.assertIn(server, up_servers)

        @chk.T(ServerTest, server=server)
        def _test_server_ssh(self, server):
            """Check if SSH port is open: {server}."""
            self.assertTrue(chk.telnet(server, 22))

    # TODO: implement test that for each partition sum of available capacity
    #       is not below partition threshold.

    return [LdapSyncTest, ServerTest]
