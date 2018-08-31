"""Unit test for pivot_root module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

import mock
import pkg_resources

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

from treadmill import pivot_root
import treadmill.fs.linux


def _test_data(name):
    data_path = os.path.join('data', name)
    with pkg_resources.resource_stream(__name__, data_path) as f:
        return f.read()


class PivotRootTest(unittest.TestCase):
    """pivot root module test"""

    MOUNTINFO = _test_data('mountinfo_pivotroot.data').decode()

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('io.open', mock.mock_open(read_data=MOUNTINFO))
    @mock.patch('treadmill.pivot_root._move_mount')
    def test_move_mounts(self, move_mount_mock):
        """Test generate sorted mounts from mountinfo file
        """
        # pylint: disable=protected-access
        sorted_mounts = pivot_root.move_mounts('/.old-pivot')
        move_mount_mock.assert_called_with(
            '/.old-pivot',
            treadmill.fs.linux.MountEntry(
                mount_id=515, parent_id=514,
                source='none',
                target='/.old-pivot/proc',
                fs_type='proc',
                mnt_opts={'nodev', 'noexec', 'relatime', 'nosuid', 'rw'}
            )
        )

        expected = [
            treadmill.fs.linux.MountEntry(
                mount_id=541, parent_id=503,
                source='/dev/sda3',
                target='/.old-pivot/a',
                fs_type='xfs',
                mnt_opts={'noatime', 'attr2', 'inode64', 'noquota', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=505, parent_id=504,
                source='tmpfs',
                target='/.old-pivot/dev/shm',
                fs_type='tmpfs',
                mnt_opts={'nodev', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=513, parent_id=509,
                source='nfsd',
                target='/.old-pivot/proc/fs/nfsd',
                fs_type='nfsd',
                mnt_opts={'relatime', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=533, parent_id=503,
                source='tmpfs',
                target='/.old-pivot/run',
                fs_type='tmpfs',
                mnt_opts={'nodev', 'mode=755', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=518, parent_id=516,
                source='tmpfs',
                target='/.old-pivot/sys/fs/cgroup',
                fs_type='tmpfs',
                mnt_opts={'nodev', 'noexec', 'mode=755', 'nosuid', 'ro'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=504, parent_id=503,
                source='devtmpfs',
                target='/.old-pivot/dev',
                fs_type='devtmpfs',
                mnt_opts={'size=8123280k', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=514, parent_id=509,
                source='none',
                target='/.old-pivot/proc',
                fs_type='proc',
                mnt_opts={'nodev', 'noexec', 'relatime', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=516, parent_id=503,
                source='sysfs',
                target='/.old-pivot/sys',
                fs_type='sysfs',
                mnt_opts={'nodev', 'noexec', 'relatime', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=509, parent_id=503,
                source='proc',
                target='/.old-pivot/proc',
                fs_type='proc',
                mnt_opts={'nodev', 'noexec', 'relatime', 'nosuid', 'rw'}
            ),
            treadmill.fs.linux.MountEntry(
                mount_id=503, parent_id=545,
                source='/dev/sda3',
                target='/.old-pivot',
                fs_type='xfs',
                mnt_opts={'noatime', 'attr2', 'inode64', 'noquota', 'rw'}
            ),
        ]
        self.assertEqual(sorted_mounts, expected)


if __name__ == '__main__':
    unittest.main()
