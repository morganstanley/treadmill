"""Unit test for treadmill.ad._servers.
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

import mock
import yaml

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import dirwatch
from treadmill.ad import _servers as servers


class ServersTest(unittest.TestCase):
    """Mock test for treadmill.ad._servers.ServersWatch.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.servers_dir = os.path.join(self.root, 'servers')
        os.mkdir(self.servers_dir)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('ldap3.Connection', mock.Mock())
    def test_sync(self):
        """Test _servers.ServersWatch.sync."""
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
                'partition': 'partition2'
            }, f)

        with io.open(os.path.join(self.servers_dir, 'server3.other.com'),
                     'w') as f:
            yaml.dump({
                'a': '1',
                'b': '2',
                'partition': 'partition1'
            }, f)

        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info['hostname'])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added)
        watch.sync()

        self.assertEqual(added_servers, set(['server1.ad.com',
                                             'server2.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertEqual(server_info[servers.DN_KEY],
                         'CN=server1,DC=AD,DC=COM')

        self.assertEqual(2, len(watch.get_all_server_info()))

    @mock.patch('ldap3.Connection', mock.Mock())
    def test_on_created(self):
        """Test _servers.ServersWatch._on_created."""
        # Access protected module
        # pylint: disable=W0212
        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info['hostname'])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added)
        watch.sync()

        path = os.path.join(self.servers_dir, 'server1.ad.com')
        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        watch._on_created(path)

        self.assertEqual(added_servers, set(['server1.ad.com']))

    @mock.patch('ldap3.Connection', mock.Mock())
    def test_on_modified(self):
        """Test _servers.ServersWatch._on_modified."""
        # Access protected module
        # pylint: disable=W0212
        path = os.path.join(self.servers_dir, 'server1.ad.com')
        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info[servers.DC_KEY])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added)
        watch.sync()

        self.assertEqual(added_servers, set(['dc.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertEqual(server_info[servers.DC_KEY],
                         'dc.ad.com')

        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc2.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        watch._on_modified(path)

        # server_added was not called a second time
        self.assertEqual(added_servers, set(['dc.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertEqual(server_info[servers.DC_KEY],
                         'dc2.ad.com')

    # Invalid method name
    # pylint: disable=C0103
    @mock.patch('ldap3.Connection', mock.Mock())
    def test_on_modified_parition_included(self):
        """Test _servers.ServersWatch._on_modified."""
        # Access protected module
        # pylint: disable=W0212
        path = os.path.join(self.servers_dir, 'server1.ad.com')
        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition2'
            }, f)

        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info['hostname'])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added)
        watch.sync()

        self.assertEqual(added_servers, set())

        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        watch._on_modified(path)

        self.assertEqual(added_servers, set(['server1.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertEqual(server_info[servers.DC_KEY],
                         'dc.ad.com')

    # Invalid method name
    # pylint: disable=C0103
    @mock.patch('ldap3.Connection', mock.Mock())
    def test_on_modified_parition_not_included(self):
        """Test _servers.ServersWatch._on_modified."""
        # Access protected module
        # pylint: disable=W0212
        path = os.path.join(self.servers_dir, 'server1.ad.com')
        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info['hostname'])

        deleted_servers = set()

        def _server_deleted(server_info):
            deleted_servers.add(server_info['hostname'])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added, _server_deleted)
        watch.sync()

        self.assertEqual(added_servers, set(['server1.ad.com']))
        self.assertEqual(deleted_servers, set())

        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition2'
            }, f)

        watch._on_modified(path)

        self.assertEqual(added_servers, set(['server1.ad.com']))
        self.assertEqual(deleted_servers, set(['server1.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertIsNone(server_info)

    @mock.patch('ldap3.Connection', mock.Mock())
    def test_on_deleted(self):
        """Test _servers.ServersWatch._on_deleted."""
        # Access protected module
        # pylint: disable=W0212
        path = os.path.join(self.servers_dir, 'server1.ad.com')
        with io.open(path, 'w') as f:
            yaml.dump({
                servers.DC_KEY: 'dc.ad.com',
                servers.DN_KEY: 'CN=server1,DC=AD,DC=COM',
                'partition': 'partition1'
            }, f)

        dirwatcher = dirwatch.DirWatcher()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        added_servers = set()

        def _server_added(server_info):
            added_servers.add(server_info['hostname'])

        deleted_servers = set()

        def _server_deleted(server_info):
            deleted_servers.add(server_info['hostname'])

        watch = servers.ServersWatch(dispatcher, self.root, 'partition1',
                                     _server_added, _server_deleted)
        watch.sync()

        self.assertEqual(added_servers, set(['server1.ad.com']))
        self.assertEqual(deleted_servers, set())

        watch._on_deleted(path)

        self.assertEqual(added_servers, set(['server1.ad.com']))
        self.assertEqual(deleted_servers, set(['server1.ad.com']))

        server_info = watch.get_server_info('server1.ad.com')
        self.assertIsNone(server_info)


if __name__ == '__main__':
    unittest.main()
