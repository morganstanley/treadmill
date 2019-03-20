"""Unit test for treadmill.sproc.zk2fs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import unittest
import mock

import kazoo

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.sproc import zk2fs
from treadmill.zksync import utils


class Zk2FsTest(unittest.TestCase):
    """Test treadmill.sproc.zk2fs"""

    @mock.patch('treadmill.sproc.zk2fs.fs', mock.Mock())
    def test_on_add_identity(self):
        """Test _on_add_identity()"""
        # pylint: disable=protected-access
        zksync_mock = mock.Mock()
        zk2fs._on_add_identity(zksync_mock, '/foo/bar')

        self.assertTrue(zksync_mock.sync_children.called)
        self.assertFalse(zksync_mock.sync_data.called)

        zksync_mock.reset_mock()
        zksync_mock.fpath.return_value = 'zkfs_root/foo/bar'
        zk2fs._on_add_identity(zksync_mock, '/foo/bar', True)

        self.assertTrue(zksync_mock.sync_children.called)
        zksync_mock.sync_data.assert_called_once_with(
            '/foo/bar',
            os.path.join('zkfs_root/foo/bar', utils.NODE_DATA_FILE),
            watch=True)

        zksync_mock.sync_data.side_effect = kazoo.client.NoNodeError
        # exception should be handled
        zk2fs._on_add_identity(zksync_mock, '/foo/bar', True)


if __name__ == '__main__':
    unittest.main()
