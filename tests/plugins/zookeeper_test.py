"""
Unit test for zookeeper plugin
"""
import unittest
import mock
from treadmill.plugins import zookeeper


class ZookeeperTest(unittest.TestCase):
    @mock.patch('kazoo.client.KazooClient')
    def test_connect_without_connargs(self, kazooClientMock):
        zkurl = 'zookeeper://foo@123:21'

        zookeeper.connect(zkurl, {})

        kazooClientMock.assert_called_once_with(
            hosts='123:21',
            sasl_data={
                'service': 'zookeeper',
                'mechanisms': ['GSSAPI']
            })

    @mock.patch('kazoo.client.KazooClient')
    def test_connect_with_connargs(self, kazooClientMock):
        zkurl = 'zookeeper://foobar:123'
        connargs = {
            'hosts': 'foobar:123',
            'sasl_data': {
                'service': 'foo',
                'mechanisms': 'bar'
            }
        }

        zookeeper.connect(zkurl, connargs)

        kazooClientMock.assert_called_once_with(
            hosts='foobar:123',
            sasl_data={
                'service': 'foo',
                'mechanisms': 'bar'
            })

    @mock.patch('kazoo.security.make_acl')
    def test_make_user_acl(self, makeAclMock):
        zookeeper.make_user_acl('foo', 'rw')

        makeAclMock.assert_called_once_with(
            scheme='sasl', credential='foo', read=True,
            write=True, create=False, delete=False, admin=False
        )

    @mock.patch('kazoo.security.make_acl')
    def test_make_role_acl_with_valid_role(self, makeAclMock):
        zookeeper.make_role_acl('servers', 'ra')

        makeAclMock.assert_called_once_with(
            scheme='sasl', credential='role/servers', read=True,
            write=False, delete=False, create=False, admin=True
        )

    def test_make_role_acl_with_invalid_role(self):
        with self.assertRaises(AssertionError):
            zookeeper.make_role_acl('foo', 'rwc')

    @mock.patch('kazoo.security.make_acl')
    def test_make_host_acl(self, makeAclMock):
        zookeeper.make_host_acl('foo@123', 'rdwca')

        makeAclMock.assert_called_once_with(
            scheme='sasl', credential='host/foo@123', read=True,
            write=True, delete=True, create=True, admin=True
        )
