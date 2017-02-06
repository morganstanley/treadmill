"""Unit test for fs - configuring unshared chroot.
"""

import unittest

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
        # missing search base.
        # TODO: renable this test once we can firgure out why ctx0.ldap.conn is
        # mocked when running with nosetest and Train
        # ctx0 = context.Context()
        # self.assertRaises(context.ContextError, ctx0.resolve, 'somecell')

        # Missing ldap url
        ctx1 = context.Context()
        ctx1.ldap.search_base = 'ou=treadmill,ou=test'
        # TODO: renable this test once we can firgure out why ctx0.ldap.conn is
        # mocked when running with nosetest and Train
        # self.assertRaises(context.ContextError, ctx1.resolve, 'somecell')

        # Cell not defined in LDAP.
        ctx2 = context.Context()
        ctx2.ldap.search_base = 'ou=treadmill,ou=test'
        ctx2.ldap.url = 'ldap://foo:1234'
        treadmill.admin.Cell.get.side_effect = ldap3.LDAPNoSuchObjectResult
        self.assertRaises(context.ContextError, ctx2.resolve, 'somecell')

        # Cell defined in LDAP
        ctx3 = context.Context()
        ctx3.ldap.search_base = 'ou=treadmill,ou=test'
        ctx3.ldap.url = 'ldap://foo:1234'

        treadmill.admin.Cell.get.side_effect = None
        treadmill.admin.Cell.get.return_value = {
            'username': 'tmtest',
            'masters': [
                {'hostname': 'xxx', 'zk-client-port': 123},
                {'hostname': 'yyy', 'zk-client-port': 345},
            ]
        }
        ctx3.resolve('somecell')
        self.assertEqual(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx3.zk.url
        )

    @mock.patch('treadmill.admin.Admin.connect', mock.Mock())
    @mock.patch('treadmill.dnsutils.txt', mock.Mock(return_value=[]))
    @mock.patch('treadmill.dnsutils.srv', mock.Mock(return_value=[]))
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    def test_dns_resolve(self):
        """Test lazy resolve logic."""
        # missing search base.
        # TODO: renable this test once we can firgure out why ctx0.ldap.conn is
        # mocked when running with nosetest and Train
        # ctx0 = context.Context()
        # self.assertRaises(context.ContextError, ctx0.resolve, 'somecell')

        ctx1 = context.Context()
        ctx1.ldap.search_base = 'ou=treadmill,ou=test'

        treadmill.dnsutils.txt.return_value = [
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
        ]
        treadmill.dnsutils.srv.return_value = [
            ('ldaphost', 1234, 10, 10)
        ]
        ctx1.resolve('somecell')
        self.assertEqual(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx1.zk.url
        )
        self.assertEqual(
            'ldap://ldaphost:1234',
            ctx1.ldap.url
        )

        # Test automatic resolve invocation
        ctx2 = context.Context()
        ctx2.ldap.search_base = 'ou=treadmill,ou=test'
        ctx2.cell = 'somecell'
        # Disable E1102: not callable
        ctx2.zk.conn()  # pylint: disable=E1102
        self.assertEqual(
            'zookeeper://tmtest@xxx:123,yyy:345/treadmill/somecell',
            ctx2.zk.url
        )

    @mock.patch('treadmill.dnsutils.srv', mock.Mock(return_value=[]))
    def test_api_resolve(self):
        """Tests resolving API from DNS srv records."""
        treadmill.dnsutils.srv.return_value = [('xxx', 123, 1, 2),
                                               ('yyy', 234, 3, 4)]

        ctx = context.Context()
        ctx.dns_domain = 'a'
        ctx.admin_api_scope = ['ny.campus', 'na.region']
        ctx.cell = 'b'
        self.assertEqual(
            ['http://xxx:123', 'http://yyy:234'], ctx.cell_api()
        )
        treadmill.dnsutils.srv.assert_called_with(
            '_http._tcp.cellapi.b.cell.a'
        )

        self.assertEqual(['x:8080'], ctx.cell_api('x:8080'))

        ctx.cell = None
        self.assertRaises(context.ContextError, ctx.cell_api)
        self.assertEqual(['x:8080'], ctx.cell_api('x:8080'))

        ctx.cell = 'a'
        ctx.dns_domain = None
        self.assertRaises(context.ContextError, ctx.cell_api)
        self.assertEqual(['x:8080'], ctx.cell_api('x:8080'))

        ctx.dns_domain = 'a.com'
        treadmill.dnsutils.srv.return_value = []
        self.assertRaises(context.ContextError, ctx.admin_api)
        treadmill.dnsutils.srv.assert_has_calls([
            mock.call('_http._tcp.adminapi.ny.campus.a.com'),
            mock.call('_http._tcp.adminapi.na.region.a.com'),
        ])


if __name__ == '__main__':
    unittest.main()
