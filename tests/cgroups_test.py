"""
Unit test for cgroups module.
"""

import builtins
import io
import os
import shutil
import tempfile
import unittest

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


class CGroupsTest(unittest.TestCase):
    """Tests for teadmill.cgroups."""

    _BLKIO_THROTTLE_IOPS = os.path.join(
        os.path.dirname(__file__),
        'blkio.throttle.io_serviced.data'
    )

    _BLKIO_THROTTLE_BPS = os.path.join(
        os.path.dirname(__file__),
        'blkio.throttle.io_service_bytes.data'
    )

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

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
    @mock.patch('os.rmdir', mock.Mock())
    def test_delete_rec(self):
        """Tests recursive cgroup deletion."""
        cgroups_dir = os.path.join(self.root, 'cgroups')
        treadmill.cgroups.get_mountpoint.return_value = cgroups_dir

        group = os.path.join('treadmill', 'apps', 'test1')
        # Create a directory and subdirs for the cgroup
        os.makedirs(os.path.join(cgroups_dir, group, 'foo', 'bar', 'baz'))

        cgroups.delete('cpu', group)

        os.rmdir.assert_has_calls([
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar/baz')),
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar')),
            mock.call(os.path.join(cgroups_dir, group, 'foo')),
            mock.call(os.path.join(cgroups_dir, group)),
        ])

    @mock.patch('treadmill.cgroups.get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('builtins.open', mock.mock_open())
    def test_join(self):
        """Tests joining the cgroup."""
        group = os.path.join('treadmill', 'apps', 'test1')

        cgroups.join('cpu', group, '1234')

        builtins.open.assert_called_once_with(
            '/cgroups/treadmill/apps/test1/tasks', 'w+')
        builtins.open().write.assert_called_once_with('1234')

    @mock.patch('treadmill.cgroups.mounted_subsystems',
                mock.Mock(return_value={'cpu': '/cgroup/cpu'}))
    @mock.patch('treadmill.cgroups.mount', mock.Mock())
    def test_ensure_mounted_missing(self):
        """Checks that missing subsystem is mounted."""
        cgroups.ensure_mounted(['cpu', 'memory'])
        treadmill.cgroups.mount.assert_called_with('memory')

    @mock.patch('builtins.open',
                mock.Mock(return_value=io.StringIO(PROCCGROUPS)))
    def test_available_subsystems(self):
        """Test functions """
        subsystems = cgroups.available_subsystems()
        self.assertEqual(['cpu', 'cpuacct', 'memory'], subsystems)

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(side_effect=['0', '', '1024', '512']))
    def test_create_treadmill_cgroups(self):
        """Test the creation of core treadmill cgroups"""
        system_cpu_shares = 50
        treadmill_cpu_shares = 50
        treadmill_core_cpu_shares = 10
        treadmill_apps_cpu_shares = 90
        treadmill_mem = 1024
        treadmill_core_mem = 512
        treadmill_apps_mem = treadmill_mem - treadmill_core_mem
        cgutils.create_treadmill_cgroups(system_cpu_shares,
                                         treadmill_cpu_shares,
                                         treadmill_core_cpu_shares,
                                         treadmill_apps_cpu_shares,
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
                 mock.call('memory', 'treadmill',
                           'memory.use_hierarchy', '1'),
                 mock.call('memory', 'treadmill',
                           'memory.limit_in_bytes', treadmill_mem),
                 mock.call('memory', 'treadmill',
                           'memory.memsw.limit_in_bytes', treadmill_mem),
                 mock.call('memory', 'treadmill',
                           'memory.oom_control', '0'),
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

    # @mock.patch('os.kill', mock.Mock())
    # def test_kill_apps_in_cgroup(self):
    #     """Make sure we kill all the stale apps."""
    #     os.mkdir(os.path.join(self.root, 'a/b/c'))
    #     os.mkdir(os.path.join(self.root, 'a/b/c/XXX'))
    #     with open(os.path.join(self.root, 'a/b/c/tasks'), 'w+') as f:
    #         f.write('123\n231\n')
    #
    #    cgutils.kill_apps_in_cgroup(self.root, 'a/b/c', delete=True)
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

    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(side_effect=[10, 20, 30]))
    def test_cgrp_meminfo(self):
        """Test the grabbing of cgrp limits"""
        rv = cgutils.cgrp_meminfo('foo')
        self.assertEqual(rv, (10, 20, 30))

    @mock.patch('treadmill.cgutils.cgrps_meminfo',
                mock.Mock(side_effect=[(10, 20, 30), (20, 10, 30)]))
    def test_cgrps_meminfo(self):
        """Test the generator which grabs (usage,soft,hard)"""
        rv = cgutils.cgrps_meminfo()
        self.assertEqual(rv, (10, 20, 30))
        rv = cgutils.cgrps_meminfo()
        self.assertEqual(rv, (20, 10, 30))

    @mock.patch('treadmill.cgroups.get_value', mock.Mock())
    def test_get_blkio_bps_info(self):
        """Test reading of blkio throttle information."""

        with open(self._BLKIO_THROTTLE_BPS) as f:
            data = f.read()
            treadmill.cgroups.get_value.side_effect = [data]

        data = cgroups.get_blkio_info('mycgrp', 'bps')

        treadmill.cgroups.get_value.assert_called_with(
            'blkio', 'mycgrp', 'blkio.throttle.io_service_bytes'
        )
        self.assertEqual(
            data['253:6'],
            {
                'Read': 331776,
                'Write': 74817536,
                'Sync': 0,
                'Async': 75149312,
                'Total': 75149312,
            }
        )

    @mock.patch('treadmill.cgroups.get_value', mock.Mock())
    def test_get_blkio_iops_info(self):
        """Test reading of blkio throttle information."""

        with open(self._BLKIO_THROTTLE_IOPS) as f:
            data = f.read()
            treadmill.cgroups.get_value.side_effect = [data]

        data = cgroups.get_blkio_info('mycgrp', 'iops')

        treadmill.cgroups.get_value.assert_called_with(
            'blkio', 'mycgrp', 'blkio.throttle.io_serviced'
        )
        self.assertEqual(
            data['253:6'],
            {
                'Read': 81,
                'Write': 18266,
                'Sync': 0,
                'Async': 18347,
                'Total': 18347,
            }
        )


if __name__ == '__main__':
    unittest.main()
