"""Verifies server health.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import context
from treadmill import checkout as chk
from treadmill import presence
from treadmill import zknamespace as z


def test():
    """Create server test class."""

    zkclient = context.GLOBAL.zk.conn
    servers = [presence.server_hostname(node)
               for node in zkclient.get_children(z.SERVER_PRESENCE)]
    nodeinfo_endpoints = zkclient.get_children(z.path.endpoint_proid('root'))

    server_endpoints = dict()
    for name in nodeinfo_endpoints:
        server_endpoints[name[:name.index('#')]] = name

    class NodeinfoTest(unittest.TestCase):
        """Checks server nodeinfo API."""

    server = None
    for server in servers:

        @chk.T(NodeinfoTest, server=server, server_endpoints=server_endpoints)
        def _is_present(self, server, server_endpoints):
            """Nodeinfo is present for server: {server}."""
            self.assertIn(server, server_endpoints)

        @chk.T(NodeinfoTest, server=server, server_endpoints=server_endpoints)
        def _is_up(self, server, server_endpoints):
            """Nodeinfo is up for server: {server}."""
            hostport, _metadata = zkclient.get(z.join_zookeeper_path(
                z.ENDPOINTS, 'root', server_endpoints[server]))

            host, port = hostport.split(':')

            url = 'http://%s:%s' % (host, port)
            print(url)
            self.assertTrue(chk.connect(host, port))
            self.assertTrue(chk.url_check(url))

    return NodeinfoTest
