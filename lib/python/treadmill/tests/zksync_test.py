"""Unit test for Zookeeper to FS module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import glob
import io
import os
import shutil
import tempfile
import unittest

import kazoo
import mock

from treadmill import fs
from treadmill import utils
from treadmill.zksync import zk2fs
from treadmill.zksync import utils as zksync_utils

from treadmill.tests.testutils import mockzk


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
            with io.open(os.path.join(self.root, fpath)) as f:
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
                'x': b'1',
                'y': b'2',
                'z': b'3',
            },
        }

        self.make_mock_zk(zk_content)

        zk2fs_sync = zk2fs.Zk2Fs(kazoo.client.KazooClient(), self.root)
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
        zk_content['a']['x'] = b'123'
        zk_content['a']['q'] = b'qqq'
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

    @mock.patch('glob.glob', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_children_unordered(self):
        """Test zk2fs sync with unordered data."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212

        zk_content = {
            'a': {
                'z': b'1',
                'x': b'2',
                'y': b'3',
            },
        }

        self.make_mock_zk(zk_content)

        glob.glob.return_value = ['a/b', 'a/a', 'a/y']

        add = []
        rm = []

        zk2fs_sync = zk2fs.Zk2Fs(kazoo.client.KazooClient(), self.root)
        zk2fs_sync._children_watch('/a', ['z', 'x', 'y'],
                                   False,
                                   lambda x: add.append(os.path.basename(x)),
                                   lambda x: rm.append(os.path.basename(x)))

        # y first because its common
        self.assertSequenceEqual(['y', 'x', 'z'], add)
        self.assertSequenceEqual(['a', 'b'], rm)

    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_children_datawatch(self):
        """Test data sync."""
        # accessing protexted members.
        # pylint: disable=W0212
        zk_content = {
            'a': {
                'x': b'1',
                'y': b'2',
                'z': b'3',
            },
        }

        self.make_mock_zk(zk_content)

        zk2fs_sync = zk2fs.Zk2Fs(kazoo.client.KazooClient(), self.root)
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
                'x': b'1',
                'y': b'2',
                'z': b'3',
            },
        }
        mock_stat = collections.namedtuple('ZkStat', ['last_modified'])(0)

        self.make_mock_zk(zk_content)
        zk2fs_sync = zk2fs.Zk2Fs(kazoo.client.KazooClient(), self.root)
        fs.mkdir_safe(os.path.join(self.root, 'a'))

        event = kazoo.protocol.states.WatchedEvent(
            'CREATED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', b'aaa', mock_stat, event)

        self._check_file('a/x', 'aaa')

        event = kazoo.protocol.states.WatchedEvent(
            'DELETED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', b'aaa', mock_stat, event)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'a/x')))

        event = kazoo.protocol.states.WatchedEvent(
            'CREATED', 'CONNECTED', '/a/x')
        zk2fs_sync._data_watch('/a/x', b'aaa', mock_stat, event)
        self._check_file('a/x', 'aaa')

        zk2fs_sync._data_watch('/a/x', None, None, None)
        self.assertFalse(os.path.exists(os.path.join(self.root, 'a/x')))

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_sync_children_immutable(self):
        """Test zk2fs sync with no watch needed."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212

        zk_content = {
            'a': {
                'x': b'1',
                'y': b'2',
                'z': b'3',
            },
        }

        self.make_mock_zk(zk_content)

        zk2fs_sync = zk2fs.Zk2Fs(kazoo.client.KazooClient(), self.root)
        fs.mkdir_safe(os.path.join(self.root, 'a'))
        zk2fs_sync.sync_children('/a',
                                 watch_data=False,
                                 on_add=zk2fs_sync._default_on_add,
                                 on_del=zk2fs_sync._default_on_del,
                                 need_watch_predicate=lambda *args: False,
                                 cont_watch_predicate=lambda *args: False)
        self._check_file('a/x', '1')
        self._check_file('a/y', '2')
        self._check_file('a/z', '3')

        self.assertNotIn('/a/x', zk2fs_sync.watches)
        self.assertNotIn('/a', zk2fs_sync.watches)
        self.assertTrue(os.path.exists(os.path.join(self.root, 'a', '.done')))

        kazoo.client.KazooClient.get_children.reset_mock()
        zk2fs_sync.sync_children('/a',
                                 watch_data=False,
                                 on_add=zk2fs_sync._default_on_add,
                                 on_del=zk2fs_sync._default_on_del,
                                 need_watch_predicate=lambda *args: False,
                                 cont_watch_predicate=lambda *args: False)
        self.assertFalse(kazoo.client.KazooClient.get_children.called)

    def test_write_data(self):
        """Tests writing data to filesystem."""
        path_ok = os.path.join(self.root, 'a')
        zksync_utils.write_data(path_ok, None, 12345)
        self.assertTrue(os.path.exists(path_ok))

        path_too_long = os.path.join(self.root, 'a' * 1024)
        self.assertRaises(
            OSError,
            zksync_utils.write_data, path_too_long, None, 12345)
        self.assertFalse(os.path.exists(path_too_long))

        zksync_utils.write_data(path_too_long, None, 12345, raise_err=False)
        self.assertFalse(os.path.exists(path_too_long))

    def test_wait_for_ready(self):
        """Test wait for ready
        """
        modified = os.path.join(self.root, '.modified')
        utils.touch(modified)
        self.assertEqual(zksync_utils.wait_for_ready(self.root), modified)


if __name__ == '__main__':
    unittest.main()
