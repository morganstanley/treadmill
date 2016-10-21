"""Unit test for Zookeeper to FS module
"""

import collections
import os
import shutil
import tempfile
import unittest

import kazoo
import mock

from treadmill import fs
from treadmill import zksync
from treadmill.test import mockzk


class ZkSyncTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.zksync"""

    def setUp(self):
        """Setup common test variables"""

        super(ZkSyncTest, self).setUp()
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        super(ZkSyncTest, self).tearDown()

    def _check_file(self, fpath, content=None):
        """Check that file exists and content matches (if specified)."""
        self.assertTrue(os.path.exists(os.path.join(self.root, fpath)))

        if content is not None:
            with open(os.path.join(self.root, fpath)) as f:
                self.assertTrue(content == f.read())

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_children(self):
        """Test zk2fs sync with no data."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212

        zk_content = {
            'a': {
                'x': '1',
                'y': '2',
                'z': '3',
            },
        }

        self.make_mock_zk(zk_content)

        zk2fs_sync = zksync.Zk2Fs(kazoo.client.KazooClient(), self.root)
        fs.mkdir_safe(os.path.join(self.root, 'a'))
        zk2fs_sync._children_watch('/a', ['x', 'y', 'z'],
                                   False,
                                   zk2fs_sync._default_on_add,
                                   zk2fs_sync._default_on_del)
        self._check_file('a/x', '1')
        self._check_file('a/y', '2')
        self._check_file('a/z', '3')

        self.assertNotIn('/a/x', zk2fs_sync.watches)

        # Common files are ignored in sync, 'x' content will not be updated.
        zk_content['a']['x'] = '123'
        zk_content['a']['q'] = 'qqq'
        zk2fs_sync._children_watch('/a', ['x', 'y', 'z', 'q'],
                                   False,
                                   zk2fs_sync._default_on_add,
                                   zk2fs_sync._default_on_del)

        self._check_file('a/x', '1')
        self._check_file('a/q', 'qqq')

        # Removing node from zk will delete it from file system.
        del zk_content['a']['x']
        zk2fs_sync._children_watch('/a', ['y', 'z', 'q'],
                                   False,
                                   zk2fs_sync._default_on_add,
                                   zk2fs_sync._default_on_del)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'a/x')))

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_children_datawatch(self):
        """Test data sync."""
        # accessing protexted members.
        # pylint: disable=W0212
        zk_content = {
            'a': {
                'x': '1',
                'y': '2',
                'z': '3',
            },
        }

        self.make_mock_zk(zk_content)

        zk2fs_sync = zksync.Zk2Fs(kazoo.client.KazooClient(), self.root)
        fs.mkdir_safe(os.path.join(self.root, 'a'))
        zk2fs_sync._children_watch('/a', ['x', 'y', 'z'],
                                   True,
                                   zk2fs_sync._default_on_add,
                                   zk2fs_sync._default_on_del)

        self._check_file('a/x', '1')
        self._check_file('a/y', '2')
        self._check_file('a/z', '3')

        self.assertIn('/a/x', zk2fs_sync.watches)
        self.assertIn('/a/y', zk2fs_sync.watches)
        self.assertIn('/a/z', zk2fs_sync.watches)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_data(self):
        """Test data sync."""
        # accessing protexted members.
        # pylint: disable=W0212
        zk_content = {
            'a': {
                'x': '1',
                'y': '2',
                'z': '3',
            },
        }
        mock_stat = collections.namedtuple('ZkStat', ['last_modified'])(0)

        self.make_mock_zk(zk_content)
        zk2fs_sync = zksync.Zk2Fs(kazoo.client.KazooClient(), self.root)
        fs.mkdir_safe(os.path.join(self.root, 'a'))

        event = kazoo.protocol.states.WatchedEvent(
            'CREATED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', 'aaa', mock_stat, event)

        self._check_file('a/x', 'aaa')

        event = kazoo.protocol.states.WatchedEvent(
            'DELETED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', 'aaa', mock_stat, event)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'a/x')))

        event = kazoo.protocol.states.WatchedEvent(
            'CREATED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', 'aaa', mock_stat, event)
        self._check_file('a/x', 'aaa')

        zk2fs_sync._data_watch('/a/x', None, None, None)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'a/x')))


if __name__ == '__main__':
    unittest.main()
