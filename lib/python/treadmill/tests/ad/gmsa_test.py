"""Unit test for treadmill.ad.gmsa.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import ldap3
import mock
import yaml

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import utils
from treadmill.ad import gmsa
from treadmill.ad import _servers as servers


class HostGroupWatchTest(unittest.TestCase):
    """Mock test for treadmill.ad.gmsa.HostGroupWatch.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.placement_dir = os.path.join(self.root, 'placement')
        self.servers_dir = os.path.join(self.root, 'servers')
        os.mkdir(self.placement_dir)
        os.mkdir(self.servers_dir)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa._check_ldap3_operation', mock.Mock())
    def test_sync(self, connection):
        """Test gmsa.HostGroupWatch.sync."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)
        utils.touch(os.path.join(server1_path, 'proid1.app#0000000000001'))

        server2_path = os.path.join(self.placement_dir, 'server2.ad.com')
        os.mkdir(server2_path)
        utils.touch(os.path.join(server2_path, 'proid4.app#0000000000004'))

        server3_path = os.path.join(self.placement_dir, 'server3.ad.com')
        os.mkdir(server3_path)

        server4_path = os.path.join(self.placement_dir, 'server4.ad.com')
        os.mkdir(server4_path)
        utils.touch(os.path.join(server4_path, 'proid3.app#0000000000003'))

        server5_path = os.path.join(self.placement_dir, 'server5.ad.com')
        os.mkdir(server5_path)
        utils.touch(os.path.join(server5_path, 'proid5.app#0000000000005'))
        utils.touch(os.path.join(server5_path, 'proid5.app#0000000000006'))

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server2.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server2,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server3.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server3,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server5.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server5,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': 'proid1-gmsa-hosts',
                'member': ['CN=server1,DC=AD,DC=COM']
            }},
            {'attributes': {
                'samAccountName': 'proid2-gmsa-hosts',
                'member': ['CN=server3,DC=AD,DC=COM']
            }},
            {'attributes': {
                'samAccountName': 'proid3-gmsa-hosts',
                'member': []
            }},
            {'attributes': {
                'samAccountName': 'proid4-gmsa-hosts',
                'member': []
            }},
            {'attributes': {
                'samAccountName': 'proid5-gmsa-hosts',
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 1},
            'proid2': {},
            'proid3': {},
            'proid4': {'CN=server2,DC=AD,DC=COM': 1},
            'proid5': {'CN=server5,DC=AD,DC=COM': 2},
        })

        mock_connection.modify.assert_has_calls(
            [
                mock.call('CN=proid2-gmsa-hosts,OU=test,DC=ad,DC=com',
                          {'member': [(ldap3.MODIFY_DELETE,
                                       ['CN=server3,DC=AD,DC=COM'])]}),
                mock.call('CN=proid4-gmsa-hosts,OU=test,DC=ad,DC=com',
                          {'member': [(ldap3.MODIFY_ADD,
                                       ['CN=server2,DC=AD,DC=COM'])]}),
                mock.call('CN=proid5-gmsa-hosts,OU=test,DC=ad,DC=com',
                          {'member': [(ldap3.MODIFY_ADD,
                                       ['CN=server5,DC=AD,DC=COM'])]}),
            ],
            any_order=True
        )

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa._check_ldap3_operation', mock.Mock())
    def test_on_created_placement(self, connection):
        """Test gmsa.HostGroupWatch._on_created_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': 'proid1-gmsa-hosts',
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': {},
        })

        placement_path = os.path.join(server1_path, 'proid1.app#0000000000001')
        utils.touch(placement_path)
        watch._on_created_placement(placement_path)

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 1},
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid1-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_ADD,
                                   ['CN=server1,DC=AD,DC=COM'])]}),
        ])

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa._check_ldap3_operation', mock.Mock())
    def test_on_created_same_host(self, connection):
        """Test gmsa.HostGroupWatch._on_created_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': 'proid1-gmsa-hosts',
                'member': []
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': {},
        })

        placement_path1 = os.path.join(server1_path,
                                       'proid1.app#0000000000001')
        utils.touch(placement_path1)
        watch._on_created_placement(placement_path1)

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 1},
        })

        placement_path2 = os.path.join(server1_path,
                                       'proid1.app#0000000000001')
        utils.touch(placement_path2)
        watch._on_created_placement(placement_path2)

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 2},
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid1-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_ADD,
                                   ['CN=server1,DC=AD,DC=COM'])]}),
        ])
        self.assertEqual(mock_connection.modify.call_count, 1)

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa._check_ldap3_operation', mock.Mock())
    def test_on_deleted_placement(self, connection):
        """Test gmsa.HostGroupWatch._on_deleted_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)
        placement_path = os.path.join(server1_path, 'proid1.app#0000000000001')
        utils.touch(placement_path)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': 'proid1-gmsa-hosts',
                'member': ['CN=server1,DC=AD,DC=COM']
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 1},
        })

        os.remove(placement_path)
        watch._on_deleted_placement(placement_path)

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 0},
        })

        mock_connection.modify.assert_has_calls([
            mock.call('CN=proid1-gmsa-hosts,OU=test,DC=ad,DC=com',
                      {'member': [(ldap3.MODIFY_DELETE,
                                   ['CN=server1,DC=AD,DC=COM'])]}),
        ])

    @mock.patch('ldap3.Connection')
    @mock.patch('treadmill.ad.gmsa._check_ldap3_operation', mock.Mock())
    def test_on_deleted_same_host(self, connection):
        """Test gmsa.HostGroupWatch._on_deleted_placement."""
        # Access protected module
        # pylint: disable=W0212
        server1_path = os.path.join(self.placement_dir, 'server1.ad.com')
        os.mkdir(server1_path)
        placement_path1 = os.path.join(server1_path,
                                       'proid1.app#0000000000001')
        utils.touch(placement_path1)
        placement_path2 = os.path.join(server1_path,
                                       'proid1.app#0000000000002')
        utils.touch(placement_path2)

        with io.open(os.path.join(self.servers_dir, 'server1.ad.com'),
                     'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        mock_connection = mock.MagicMock()
        connection.return_value = mock_connection
        type(mock_connection).result = mock.PropertyMock(side_effect={
            'result': 0
        })
        type(mock_connection).response = mock.PropertyMock(return_value=[
            {'attributes': {
                'samAccountName': 'proid1-gmsa-hosts',
                'member': ['CN=server1,DC=AD,DC=COM']
            }}
        ])

        watch = gmsa.HostGroupWatch(self.root, 'partition1',
                                    'OU=test,DC=ad,DC=com', '{}-gmsa-hosts')
        watch._sync()

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 2},
        })

        os.remove(placement_path2)
        watch._on_deleted_placement(placement_path2)

        self.assertEqual(watch._proids, {
            'proid1': {'CN=server1,DC=AD,DC=COM': 1},
        })

        mock_connection.modify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
