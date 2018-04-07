"""
Unit test for zookeeper plugin
"""
import unittest
import mock
from treadmill.plugins import zookeeper


class ZookeeperTest(unittest.TestCase):
    """Tests Zookeeper plugin."""

    @mock.patch('kazoo.client.KazooClient')
    def test_connect_without_connargs(self, kazoo_clien_mock):
        """Test connect."""
        zkurl = 'zookeeper://foo@123:21'

        zookeeper.connect(zkurl, {})

        kazoo_clien_mock.assert_called_once_with(
            hosts='123:21',
            sasl_data={
                'service': 'zookeeper',
                'mechanisms': ['GSSAPI']
            })

    @mock.patch('kazoo.client.KazooClient')
    def test_connect_with_connargs(self, kazoo_clien_mock):
        """Test connect with args."""
        zkurl = 'zookeeper://foobar:123'
        connargs = {
            'hosts': 'foobar:123',
            'sasl_data': {
                'service': 'foo',
                'mechanisms': 'bar'
            }
        }

        zookeeper.connect(zkurl, connargs)

        kazoo_clien_mock.assert_called_once_with(
            hosts='foobar:123',
            sasl_data={
                'service': 'foo',
                'mechanisms': 'bar'
            })

    @mock.patch('kazoo.security.make_acl')
    def test_make_user_acl(self, make_acl_mock):
        """Test constucting user acl."""
        zookeeper.make_user_acl('foo', 'rw')

        make_acl_mock.assert_called_once_with(
            scheme='sasl', credential='foo', read=True,
            write=True, create=False, delete=False, admin=False
        )

    @mock.patch('kazoo.security.make_acl')
    def test_make_role_acl(self, make_acl_mock):
        """Test constructing role acl for valid role."""
        zookeeper.make_role_acl('servers', 'ra')

        make_acl_mock.assert_called_once_with(
            scheme='sasl', credential='role/servers', read=True,
            write=False, delete=False, create=False, admin=True
        )

    def test_make_role_acl_bad_role(self):
        """Test acl with invalid role."""
        with self.assertRaises(AssertionError):
            zookeeper.make_role_acl('foo', 'rwc')

    @mock.patch('kazoo.security.make_acl')
    def test_make_host_acl(self, make_acl_mock):
        """Test host acl."""
        zookeeper.make_host_acl('foo@123', 'rdwca')

        make_acl_mock.assert_called_once_with(
            scheme='sasl', credential='host/foo@123', read=True,
            write=True, delete=True, create=True, admin=True
        )
