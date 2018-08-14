"""Unit test for cgroups module.
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

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import cgroups

from treadmill.fs import linux as fs_linux


_PROC_CGROUPS = """#subsys_name    hierarchy       num_cgroups     enabled
cpuset  4       1       0
ns      10      3       0
cpu     2       3       1
cpuacct 3       3       1
memory  7       3       1
devices 5       1       0
freezer 6       1       0
net_cls 8       1       0
blkio   1       1       0
perf_event      11      1       0
net_prio        9       1       0
"""

_PROC_CGROUP = """
11:pids:/
10:cpuacct,cpu:/
9:blkio:/
8:freezer:/
7:memory:/
6:perf_event:/
5:hugetlb:/
4:cpuset:/
3:devices:/system.slice/sshd.service
2:net_prio,net_cls:/
1:name=systemd:/system.slice/sshd.service
"""


class CGroupsTest(unittest.TestCase):
    """Tests for teadmill.cgroups.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.cgroups._available_subsystems',
                mock.Mock(return_value=[
                    'cpu', 'cpuacct', 'cpuset', 'memory', 'blkio'
                ]))
    @mock.patch('treadmill.fs.linux.list_mounts', mock.Mock(spec_set=True))
    def test_read_mounted_cgroups(self):
        """Test get mounted point.
        """

        fs_linux.list_mounts.return_value = [
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='tmpfs', target='/sys/fs/cgroup',
                fs_type='tmpfs',
                mnt_opts={
                    'mode=755',
                    'nodev',
                    'noexec',
                    'nosuid',
                    'ro',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/devices',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'devices',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/memory',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'memory',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/blkio',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'blkio',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/net_cls,net_prio',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'noexec',
                    'relatime',
                    'net_cls',
                    'rw',
                    'nosuid',
                    'nodev',
                    'net_prio',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/pids',
                fs_type='cgroup',
                mnt_opts={
                    'pids',
                    'clone_children',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/hugetlb',
                fs_type='cgroup',
                mnt_opts={
                    'hugetlb',
                    'clone_children',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/freezer',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'freezer',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/cpu,cpuacct',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'noexec',
                    'relatime',
                    'cpuacct',
                    'cpu',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/perf_event',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'noexec',
                    'relatime',
                    'rw',
                    'perf_event',
                    'nosuid',
                    'nodev',
                }
            ),
            fs_linux.MountEntry(
                mount_id=24, parent_id=17,
                source='cgroup', target='/sys/fs/cgroup/cpuset',
                fs_type='cgroup',
                mnt_opts={
                    'clone_children',
                    'cpuset',
                    'noexec',
                    'relatime',
                    'rw',
                    'nosuid',
                    'nodev',
                }
            ),
        ]

        subsystems2mounts = cgroups.read_mounted_cgroups()
        self.assertEqual(
            subsystems2mounts,
            {
                'blkio': ['/sys/fs/cgroup/blkio'],
                'cpu': ['/sys/fs/cgroup/cpu,cpuacct'],
                'cpuacct': ['/sys/fs/cgroup/cpu,cpuacct'],
                'cpuset': ['/sys/fs/cgroup/cpuset'],
                'memory': ['/sys/fs/cgroup/memory'],
            }
        )

    @mock.patch('io.open', mock.mock_open(read_data=_PROC_CGROUP.strip()))
    def test_proc_cgroups(self):
        """Test reading a process' cgroups.
        """
        io.open.return_value.__iter__ = lambda x: iter(x.readlines())

        res = cgroups.proc_cgroups()
        self.assertEqual(
            res,
            {
                'blkio': '/',
                'cpuacct,cpu': '/',
                'cpuset': '/',
                'devices': '/system.slice/sshd.service',
                'freezer': '/',
                'hugetlb': '/',
                'memory': '/',
                'name=systemd': '/system.slice/sshd.service',
                'net_prio,net_cls': '/',
                'perf_event': '/',
                'pids': '/',
            }
        )

    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(side_effect=['2', '1\n2', '-1', '']))
    def test_get_value(self):
        """Test cgroup value fetching.
        """
        value = cgroups.get_value('memory', 'foo', 'memory.usage_in_bytes')
        self.assertEqual(value, 2)

        value = cgroups.get_value('memory', 'foo', 'memory.usage_in_bytes')
        self.assertEqual(value, 1)

        value = cgroups.get_value('memory', 'foo', 'memory.usage_in_bytes')
        self.assertEqual(value, 0)

        value = cgroups.get_value('memory', 'foo', 'memory.usage_in_bytes')
        self.assertEqual(value, 0)

    @mock.patch('treadmill.cgroups._get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock(set_spec=True))
    def test_create(self):
        """Tests cgroup creation.
        """
        group = os.path.join('treadmill', 'apps', 'test1')
        cgroups.create('cpu', group)
        cgroups.create('memory', group)
        cgroups.create('cpuacct', group)
        treadmill.fs.mkdir_safe.assert_has_calls(
            [
                mock.call('/cgroups/treadmill/apps/test1'),
                mock.call('/cgroups/treadmill/apps/test1'),
                mock.call('/cgroups/treadmill/apps/test1'),
            ]
        )

    @mock.patch('treadmill.cgroups._get_mountpoint', mock.Mock())
    def test_extractpath(self):
        """Test cgroup name from a cgroup path.
        """
        # pylint: disable=W0212

        treadmill.cgroups._get_mountpoint.return_value = '/fs/cgroup/memory'
        cgrp = cgroups.extractpath('/fs/cgroup/memory/treadmill/core',
                                   'memory')
        self.assertEqual(cgrp, 'treadmill/core')

        cgrp = cgroups.extractpath('/fs/cgroup/memory/treadmill/core/foo',
                                   'memory', 'foo')
        self.assertEqual(cgrp, 'treadmill/core')

        with self.assertRaises(ValueError):
            cgroups.extractpath('/cgroup/memory/treadmill/core', 'memory')

        with self.assertRaises(ValueError):
            cgroups.extractpath('/fs/cgroup/memory/treadmill/core/foo',
                                'cpu', 'bar')

    @mock.patch('treadmill.cgroups._get_mountpoint', mock.Mock())
    @mock.patch('os.rmdir', mock.Mock())
    def test_delete(self):
        """Tests cgroup deletion.
        """
        # pylint: disable=W0212

        cgroups_dir = os.path.join(self.root, 'cgroups')
        treadmill.cgroups._get_mountpoint.return_value = cgroups_dir

        group = os.path.join('treadmill', 'apps', 'test1')
        # Create a directory for the cgroup
        os.makedirs(os.path.join(cgroups_dir, group))

        cgroups.delete('cpu', group)

        os.rmdir.assert_called_once_with(
            os.path.join(cgroups_dir, group)
        )

    @mock.patch('treadmill.cgroups._get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('io.open', mock.mock_open())
    def test_join(self):
        """Tests joining the cgroup.
        """
        group = os.path.join('treadmill', 'apps', 'test1')

        cgroups.join('cpu', group, '1234')

        io.open.assert_called_once_with(
            '/cgroups/treadmill/apps/test1/tasks', 'w')
        io.open().write.assert_called_once_with('1234')

    @mock.patch('io.open', mock.mock_open(read_data=_PROC_CGROUPS))
    def test__available_subsystems(self):
        """Test parsince available subsystems.
        """
        # pylint: disable=W0212
        io.open.return_value.__iter__ = lambda x: iter(x.readlines())

        subsystems = cgroups._available_subsystems()
        self.assertEqual(['cpu', 'cpuacct', 'memory'], subsystems)


if __name__ == '__main__':
    unittest.main()
