"""Unit test for fs - configuring unshared chroot.
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import ldap3
import mock

import treadmill
from treadmill import context


class ContextTest(unittest.TestCase):
    """Tests for teadmill.context."""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('treadmill.admin.Admin.connect', mock.Mock())
    @mock.patch('treadmill.admin.Cell.get', mock.Mock())
    @mock.patch('treadmill.dnsutils.query', mock.Mock(return_value=[]))
    def test_ldap_resolve(self):
        """Test lazy resolve logic."""
        ctx = context.Context()
        # missing search base.
        self.assertRaises(context.ContextError, ctx.resolve, 'somecell')
        ctx.ldap.search_base = 'ou=treadmill,ou=test'

        # Missing ldap url
        self.assertRaises(context.ContextError, ctx.resolve, 'somecell')

        ctx.ldap.url = 'ldap://foo:1234'

        treadmill.admin.Cell.get.side_effect = ldap3.LDAPNoSuchObjectResult
        self.assertRaises(context.ContextError, ctx.resolve, 'somecell',
                          useldap=True)

        treadmill.admin.Cell.get.side_effect = None
        treadmill.admin.Cell.get.return_value = {
            'username': 'tmtest',
            'masters': [
                {'hostname': 'xxx', 'zk-client-port': 123},
                {'hostname': 'yyy', 'zk-client-port': 345},
            ]
        }
        ctx.resolve('somecell', useldap=True)
        self.assertEquals(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx.zk.url
        )

    @mock.patch('treadmill.admin.Admin.connect', mock.Mock())
    @mock.patch('treadmill.dnsutils.txt', mock.Mock(return_value=[]))
    @mock.patch('treadmill.dnsutils.srv', mock.Mock(return_value=[]))
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    def test_dns_resolve(self):
        """Test lazy resolve logic."""
        ctx = context.Context()
        # missing search base.
        self.assertRaises(context.ContextError, ctx.resolve, 'somecell')
        ctx.ldap.search_base = 'ou=treadmill,ou=test'

        treadmill.dnsutils.txt.return_value = [
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
        ]
        treadmill.dnsutils.srv.return_value = [
            ('ldaphost', 1234, 10, 10)
        ]
        ctx.resolve('somecell')
        self.assertEquals(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx.zk.url
        )
        self.assertEquals(
            'ldap://ldaphost:1234',
            ctx.ldap.url
        )

        # Test automatic resolve invocation
        ctx_1 = context.Context()
        ctx_1.ldap.search_base = 'ou=treadmill,ou=test'
        ctx_1.cell = 'somecell'
        # Disable E1102: not callable
        ctx_1.zk.conn()  # pylint: disable=E1102
        self.assertEquals(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx_1.zk.url
        )

    @mock.patch('treadmill.dnsutils.srv', mock.Mock(return_value=[]))
    def test_api_resolve(self):
        """Tests resolving API from DNS srv records."""
        treadmill.dnsutils.srv.return_value = [('xxx', 123, 1, 2),
                                               ('yyy', 234, 3, 4)]

        ctx = context.Context()
        ctx.dns_domain = 'a'
        ctx.admin_api_scope = 'na.region'
        ctx.cell = 'b'
        self.assertEquals(['http://xxx:123', 'http://yyy:234'],
                          ctx.cell_api())
        treadmill.dnsutils.srv.assert_called_with(
            '_http._tcp.cellapi.b.cell.a'
        )

        self.assertEquals(['x:8080'], ctx.cell_api('x:8080'))

        ctx.cell = None
        self.assertRaises(context.ContextError, ctx.cell_api)
        self.assertEquals(['x:8080'], ctx.cell_api('x:8080'))

        ctx.cell = 'a'
        ctx.dns_domain = None
        self.assertRaises(context.ContextError, ctx.cell_api)
        self.assertEquals(['x:8080'], ctx.cell_api('x:8080'))


if __name__ == '__main__':
    unittest.main()
