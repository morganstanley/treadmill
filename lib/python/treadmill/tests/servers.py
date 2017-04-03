"""
Verifies server health.
"""

import unittest

from treadmill import context
from treadmill import tests as chk
from treadmill import zknamespace as z


def mk_is_present(server, server_endpoints):
    """Make is_present test function."""

    def _is_present(self):
        """Check nodeinfo endpoint registered for the server."""
        self.assertIn(server, server_endpoints)

    _is_present.__doc__ = '{} nodeinfo is present.'.format(server)
    return _is_present


def mk_is_up(zkclient, server, server_endpoints):
    """Make is up test function."""

    def _is_up(self):
        """Check nodeinfo is up."""
        hostport, _metadata = zkclient.get(z.join_zookeeper_path(
            z.ENDPOINTS, 'root', server_endpoints[server]))

        host, port = hostport.split(':')

        url = 'http://%s:%s' % (host, port)
        print url
        self.assertTrue(chk.connect(host, port))
        self.assertTrue(chk.url_check(url))

    _is_up.__doc__ = '{} nodeinfo is up.'.format(server)
    return _is_up


def test():
    """Create server test class."""

    zkclient = context.GLOBAL.zk.conn
    servers = zkclient.get_children(z.SERVER_PRESENCE)
    nodeinfo_endpoints = zkclient.get_children(z.path.endpoint_proid('root'))

    server_endpoints = dict()
    for name in nodeinfo_endpoints:
        server_endpoints[name[:name.index('#')]] = name

    class NodeinfoTest(unittest.TestCase):
        """Checks server nodeinfo API."""

    server = None
    for idx, server in enumerate(servers):
        chk.add_test(
            NodeinfoTest,
            mk_is_present(server, server_endpoints),
            '{}_present.', idx
        )
        chk.add_test(
            NodeinfoTest,
            mk_is_up(zkclient, server, server_endpoints),
            '{}_up.', idx
        )

    return NodeinfoTest
