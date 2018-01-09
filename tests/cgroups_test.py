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

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows  # pylint: disable=W0611

import mock

import treadmill
from treadmill import cgroups
from treadmill import cgutils


PROCCGROUPS = """#subsys_name    hierarchy       num_cgroups     enabled
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
net_prio        9       1       0"""

PROCMOUNTS_RH6 = """rootfs / rootfs rw 0 0
proc /proc proc rw,relatime 0 0
blkio /cgroup/blkio cgroup rw,relatime,blkio 0 0
cpu /cgroup/cpu cgroup rw,relatime,cpu 0 0
cpuacct /cgroup/cpuacct cgroup rw,relatime,cpuacct 0 0
cpuset /cgroup/cpuset cgroup rw,relatime,cpuset 0 0
devices /cgroup/devices cgroup rw,relatime,devices 0 0
"""

PROCMOUNTS_RH7 = """sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
cgroup /sys/fs/cgroup/systemd cgroup rw,nosuid,nodev,noexec,relatime,xattr 0 0
pstore /sys/fs/pstore pstore rw,nosuid,nodev,noexec,relatime 0 0
cgroup /sys/fs/cgroup/cpu,cpuacct cgroup rw,nosuid,nodev,nonexe,cpuacct,cpu 0 0
cgroup /sys/fs/cgroup/cpuset cgroup rw,nosuid,nodev,noexec,relatime,cpuset 0 0
cpuset /cgroup/cpuset cgroup rw,relatime,cpuset 0 0
"""


class CGroupsTest(unittest.TestCase):
    """Tests for teadmill.cgroups."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.cgroups.available_subsystems',
                mock.Mock(return_value=[
                    'cpu', 'cpuacct', 'cpuset', 'memory', 'blkio'
                ]))
    @mock.patch('io.open', mock.Mock(return_value=io.StringIO(PROCMOUNTS_RH6)))
    def test_read_mounted_cgroups_rh6(self):
        """Test get mounted point from rh6
        """
        subsystems2mounts = cgroups.read_mounted_cgroups()
        self.assertEqual(
            subsystems2mounts,
            {
                'blkio': ['/cgroup/blkio'],
                'cpu': ['/cgroup/cpu'],
                'cpuacct': ['/cgroup/cpuacct'],
                'cpuset': ['/cgroup/cpuset'],
            }
        )

    @mock.patch('treadmill.cgroups.available_subsystems',
                mock.Mock(return_value=[
                    'cpu', 'cpuacct', 'cpuset', 'memory', 'blkio'
                ]))
    @mock.patch('io.open', mock.Mock(return_value=io.StringIO(PROCMOUNTS_RH7)))
    def test_read_mounted_cgroups_rh7(self):
        """Test get mounted point from rh7
        """
        subsystems2mounts = cgroups.read_mounted_cgroups()
        self.assertEqual(
            subsystems2mounts,
            {
                'cpu': ['/sys/fs/cgroup/cpu,cpuacct'],
                'cpuacct': ['/sys/fs/cgroup/cpu,cpuacct'],
                'cpuset': ['/sys/fs/cgroup/cpuset', '/cgroup/cpuset']
            }
        )

    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(side_effect=['2', '1\n2', '-1', '']))
    def test_get_value(self):
        """Test cgroup value fetching"""
        value = cgroups.get_value('memory', 'foo', 'memory,usage_in_bytes')
        self.assertEqual(value, 2)

        value = cgroups.get_value('memory', 'foo', 'memory,usage_in_bytes')
        self.assertEqual(value, 1)

        value = cgroups.get_value('memory', 'foo', 'memory,usage_in_bytes')
        self.assertEqual(value, 0)

        value = cgroups.get_value('memory', 'foo', 'memory,usage_in_bytes')
        self.assertEqual(value, 0)

    @mock.patch('treadmill.cgroups.get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('os.makedirs', mock.Mock())
    def test_create(self):
        """Tests cgroup creation."""
        group = os.path.join('treadmill', 'apps', 'test1')
        cgroups.create('cpu', group)
        cgroups.create('memory', group)
        cgroups.create('cpuacct', group)
        os.makedirs.assert_has_calls(
            [mock.call('/cgroups/treadmill/apps/test1'),
             mock.call('/cgroups/treadmill/apps/test1'),
             mock.call('/cgroups/treadmill/apps/test1')])

    @mock.patch('treadmill.cgroups.get_mountpoint', mock.Mock())
    def test_extractpath(self):
        """ test cgroup name from a cgroup path"""
        treadmill.cgroups.get_mountpoint.return_value = '/fs/cgroup/memory'
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

    @mock.patch('treadmill.cgroups.get_mountpoint', mock.Mock())
    @mock.patch('os.rmdir', mock.Mock())
    def test_delete(self):
        """Tests cgroup deletion."""
        cgroups_dir = os.path.join(self.root, 'cgroups')
        treadmill.cgroups.get_mountpoint.return_value = cgroups_dir

        group = os.path.join('treadmill', 'apps', 'test1')
        # Create a directory for the cgroup
        os.makedirs(os.path.join(cgroups_dir, group))

        cgroups.delete('cpu', group)

        os.rmdir.assert_called_once_with(
            os.path.join(cgroups_dir, group)
        )

    @mock.patch('treadmill.cgroups.get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('io.open', mock.mock_open())
    def test_join(self):
        """Tests joining the cgroup."""
        group = os.path.join('treadmill', 'apps', 'test1')

        cgroups.join('cpu', group, '1234')

        io.open.assert_called_once_with(
            '/cgroups/treadmill/apps/test1/tasks', 'w')
        io.open().write.assert_called_once_with('1234')

    @mock.patch('treadmill.cgroups.mounted_subsystems',
                mock.Mock(return_value={'cpu': '/cgroup/cpu'}))
    @mock.patch('treadmill.cgroups.mount', mock.Mock())
    def test_ensure_mounted_missing(self):
        """Checks that missing subsystem is mounted."""
        cgroups.ensure_mounted(['cpu', 'memory'])
        treadmill.cgroups.mount.assert_called_with('memory')

    @mock.patch('io.open', mock.Mock(return_value=io.StringIO(PROCCGROUPS)))
    def test_available_subsystems(self):
        """Test functions """
        subsystems = cgroups.available_subsystems()
        self.assertEqual(['cpu', 'cpuacct', 'memory'], subsystems)

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(side_effect=['0', '0', '', '1024', '512']))
    @mock.patch('treadmill.sysinfo.cpu_count',
                mock.Mock(return_value=4))
    def test_create_treadmill_cgroups(self):
        """Test the creation of core treadmill cgroups"""
        system_cpu_shares = 50
        treadmill_cpu_shares = 50
        treadmill_core_cpu_shares = 10
        treadmill_apps_cpu_shares = 90
        treadmill_cpu_cores = 0
        treadmill_mem = 1024
        treadmill_core_mem = 512
        treadmill_apps_mem = treadmill_mem - treadmill_core_mem
        cgutils.create_treadmill_cgroups(system_cpu_shares,
                                         treadmill_cpu_shares,
                                         treadmill_core_cpu_shares,
                                         treadmill_apps_cpu_shares,
                                         treadmill_cpu_cores,
                                         treadmill_mem,
                                         treadmill_core_mem)
        calls = [mock.call('cpu', 'system'),
                 mock.call('cpu', 'treadmill'),
                 mock.call('cpu', 'treadmill/core'),
                 mock.call('cpu', 'treadmill/apps'),
                 mock.call('cpuacct', 'system'),
                 mock.call('cpuacct', 'treadmill'),
                 mock.call('cpuacct', 'treadmill/core'),
                 mock.call('cpuacct', 'treadmill/apps'),
                 mock.call('cpuset', 'system'),
                 mock.call('cpuset', 'treadmill'),
                 mock.call('memory', 'system'),
                 mock.call('memory', 'treadmill'),
                 mock.call('memory', 'treadmill/core'),
                 mock.call('memory', 'treadmill/apps')]
        treadmill.cgroups.create.assert_has_calls(calls)
        calls = [mock.call('cpu', 'treadmill',
                           'cpu.shares', treadmill_cpu_shares),
                 mock.call('cpu', 'system',
                           'cpu.shares', system_cpu_shares),
                 mock.call('cpu', 'treadmill/core',
                           'cpu.shares', treadmill_core_cpu_shares),
                 mock.call('cpu', 'treadmill/apps',
                           'cpu.shares', treadmill_apps_cpu_shares),
                 mock.call('cpuset', 'system',
                           'cpuset.mems', 0),
                 mock.call('cpuset', 'treadmill',
                           'cpuset.mems', 0),
                 mock.call('cpuset', 'treadmill',
                           'cpuset.cpus', '0-3'),
                 mock.call('cpuset', 'system',
                           'cpuset.cpus', '0-3'),
                 mock.call('memory', 'system',
                           'memory.move_charge_at_immigrate', 1),
                 mock.call('memory', 'treadmill',
                           'memory.move_charge_at_immigrate', 1),
                 mock.call('memory', 'treadmill',
                           'memory.use_hierarchy', '1'),
                 mock.call('memory', 'treadmill',
                           'memory.limit_in_bytes', treadmill_mem),
                 mock.call('memory', 'treadmill',
                           'memory.memsw.limit_in_bytes', treadmill_mem),
                 mock.call('memory', 'treadmill',
                           'memory.oom_control', '0'),
                 mock.call('memory', 'treadmill/core',
                           'memory.move_charge_at_immigrate', 1),
                 mock.call('memory', 'treadmill/apps',
                           'memory.move_charge_at_immigrate', 1),
                 mock.call('memory', 'treadmill/core',
                           'memory.limit_in_bytes', treadmill_core_mem),
                 mock.call('memory', 'treadmill/core',
                           'memory.memsw.limit_in_bytes', treadmill_core_mem),
                 mock.call('memory', 'treadmill/core',
                           'memory.soft_limit_in_bytes', treadmill_core_mem),
                 mock.call('memory', 'treadmill/apps',
                           'memory.limit_in_bytes', treadmill_apps_mem),
                 mock.call('memory', 'treadmill/apps',
                           'memory.memsw.limit_in_bytes', treadmill_apps_mem)]
        treadmill.cgroups.set_value.assert_has_calls(calls)

    # TODO: Remove or fix
    # @mock.patch('os.kill', mock.Mock())
    # def test_kill_apps_in_cgroup(self):
    #     """Make sure we kill all the stale apps."""
    #     os.mkdir(os.path.join(self.root, 'a/b/c'))
    #     os.mkdir(os.path.join(self.root, 'a/b/c/XXX'))
    #     with open(os.path.join(self.root, 'a/b/c/tasks'), 'w+') as f:
    #         f.write('123\n231\n')
    #
    #    cgutils.kill_apps_in_cgroup(self.root, 'a/b/c', delete_cgrp=True)
    #    os.kill.assert_has_calls([mock.call(123, signal.SIGKILL),
    #                              mock.call(321, signal.SIGKILL)])
    #    self.assertFalse(os.path.exists(os.path.join(self.root, 'a/b/c')))

    @mock.patch('treadmill.cgroups.set_value',
                mock.Mock())
    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(return_value=512))
    @mock.patch('treadmill.cgroups.makepath',
                mock.Mock(return_value='/cgroup/memory/treadmill/apps'))
    @mock.patch('treadmill.cgutils.total_soft_memory_limits',
                mock.Mock(return_value=1024))
    @mock.patch('os.listdir',
                mock.Mock(return_value=['a', 'b']))
    @mock.patch('os.path.isdir',
                mock.Mock(return_value=True))
    def test_reset_mem_limit_in_bytes(self):
        """Make sure we are setting hardlimits right"""
        cgutils.reset_memory_limit_in_bytes()
        mock_calls = [mock.call('memory',
                                'treadmill/apps',
                                'memory.limit_in_bytes'),
                      mock.call('memory',
                                'treadmill/apps/a',
                                'memory.soft_limit_in_bytes'),
                      mock.call('memory',
                                'treadmill/apps/b',
                                'memory.soft_limit_in_bytes')]
        cgroups.get_value.assert_has_calls(mock_calls)
        mock_calls = [mock.call('memory',
                                'treadmill/apps/a',
                                'memory.limit_in_bytes',
                                512),
                      mock.call('memory',
                                'treadmill/apps/a',
                                'memory.memsw.limit_in_bytes',
                                512),
                      mock.call('memory',
                                'treadmill/apps/b',
                                'memory.limit_in_bytes',
                                512),
                      mock.call('memory',
                                'treadmill/apps/b',
                                'memory.memsw.limit_in_bytes',
                                512)]

        cgroups.set_value.assert_has_calls(mock_calls)

    @mock.patch('treadmill.cgutils.set_memory_hardlimit', mock.Mock())
    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(return_value=512))
    @mock.patch('treadmill.cgroups.makepath',
                mock.Mock(return_value='/cgroup/memory/treadmill/apps'))
    @mock.patch('treadmill.cgutils.total_soft_memory_limits',
                mock.Mock(return_value=1024))
    @mock.patch('os.listdir',
                mock.Mock(return_value=['a']))
    @mock.patch('os.path.isdir',
                mock.Mock(return_value=True))
    def test_reset_mem_limit_kill(self):
        """Make sure we kill groups when we cannot lower their hardlimits."""
        treadmill.cgutils.set_memory_hardlimit.side_effect = \
            cgutils.TreadmillCgroupError('test')

        res = cgutils.reset_memory_limit_in_bytes()

        self.assertEqual(res, ['a'])


if __name__ == '__main__':
    unittest.main()
