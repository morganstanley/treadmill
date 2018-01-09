"""Unit test for Zookeeper helper - testing zk connection and leader election.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import io
import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows  # pylint: disable=W0611
from tests.testutils import mockzk

import kazoo
import kazoo.client
import mock

from treadmill import zkutils
from treadmill import versionmgr


class VersionMgrTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.versionmgr."""

    @mock.patch('treadmill.zkutils.connect', mock.Mock(
        return_value=kazoo.client.KazooClient()))
    @mock.patch('kazoo.client.KazooClient.start', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.add_listener', mock.Mock())
    def setUp(self):
        super(VersionMgrTest, self).setUp()
        self.zkclient = zkutils.connect('zk')
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_verify(self):
        """Tests version verification."""
        zk_content = {
            'servers': {
                's1': {
                }
            },
            'version': {
                's1': {
                    'digest': '1234',
                }
            },
        }
        self.make_mock_zk(zk_content)
        self.assertEqual(
            [],
            versionmgr.verify(self.zkclient, '1234', ['s1'])
        )
        self.assertEqual(
            ['s1'],
            versionmgr.verify(self.zkclient, '3333', ['s1'])
        )
        self.assertEqual(
            [],
            versionmgr.verify(self.zkclient, '3333', ['s2'])
        )

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_upgrade(self):
        """Tests version verification."""
        zk_content = {
            'servers': {
                's1': {
                }
            },
            'version': {
                's1': {
                    'digest': '1234',
                },
                's2': {
                    'digest': '1234',
                },
            },
        }
        self.make_mock_zk(zk_content)

        # In 100% successful scenario, version nodes will be recreated by
        # version monitor.
        #
        # In the test, version for s1 will not be recreated, and s1 will be
        # reported as failure.
        self.assertEqual(
            ['s1'],
            versionmgr.upgrade(
                self.zkclient,
                '3456',
                ['s1', 's2'],
                10,
                1,
                False
            )
        )
        self.assertNotIn('s1', zk_content['version'])
        self.assertNotIn('s2', zk_content['version'])

    @mock.patch('hashlib.sha256', mock.Mock())
    def test_checksum_dir(self):
        """Test checksum'ing of directory structure.
        """
        # Setup directory
        # /.git
        os.makedirs(os.path.join(self.root, '.git'))
        # /common/foo/
        os.makedirs(os.path.join(self.root, 'common'))
        os.makedirs(os.path.join(self.root, 'common', 'foo'))
        # /common/foo/bar
        with io.open(os.path.join(self.root, 'common', 'foo', 'bar'), 'w'):
            pass
        # /common/foo/baz -> bar
        os.symlink('bar',
                   os.path.join(self.root, 'common', 'foo', 'baz'))
        # /foodir -> common/foo
        os.symlink(os.path.join('common', 'foo'),
                   os.path.join(self.root, 'foodir'))
        # /foo/bar -> ../common/foo/bar
        os.makedirs(os.path.join(self.root, 'foo'))
        os.symlink(os.path.join('..', 'common', 'foo', 'bar'),
                   os.path.join(self.root, 'foo', 'bar'))
        # /otherdir -> /dir
        os.symlink('/dir',
                   os.path.join(self.root, 'otherdir'))
        mock_checksum = hashlib.sha256.return_value

        versionmgr.checksum_dir(self.root)

        mock_checksum.update.assert_has_calls(
            [
                # XXX(boysson): Figure out how to test this
                # mock.call('/common/foo/bar <mode> <size> <mtime> <ctime>'),
                mock.call(b'/common/foo/baz -> bar'),
                mock.call(b'/foodir -> common/foo'),
                mock.call(b'/foo/bar -> ../common/foo/bar'),
                mock.call(b'/otherdir -> /dir'),
            ],
            any_order=True
        )
        self.assertEqual(mock_checksum.update.call_count, 5)


if __name__ == '__main__':
    unittest.main()
