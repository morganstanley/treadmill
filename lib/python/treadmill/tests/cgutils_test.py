"""Unit test for cgutils module.
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
import pkg_resources

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import cgutils
from treadmill import cgroups


def _test_data(name):
    data_path = os.path.join('data', name)
    with pkg_resources.resource_stream(__name__, data_path) as f:
        return f.read().decode()


class CGutilsTest(unittest.TestCase):
    """Tests for teadmill.cgutils.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._blkio_throttle_iops = _test_data(
            'blkio.throttle.io_serviced.data'
        )
        self._blkio_throttle_bps = _test_data(
            'blkio.throttle.io_service_bytes.data'
        )
        self._blkio_bps_empty = _test_data('blkio.io_service_bytes.empty.data')
        self._blkio_sectors_empty = _test_data('blkio.sectors.empty.data')

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('treadmill.cgroups.makepath', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.syscall.eventfd.eventfd',
                mock.Mock(return_value=42))
    def test_get_memory_oom_eventfd(self):
        """Test registration of oom events.
        """
        treadmill.cgroups.makepath.return_value = 'mock_oom_control'
        mock_handle = io.open.return_value
        mock_handle.fileno.return_value = 43

        res = cgutils.get_memory_oom_eventfd('some_cgrp')

        treadmill.syscall.eventfd.eventfd.assert_called_with(
            0, treadmill.syscall.eventfd.EFD_CLOEXEC
        )
        treadmill.cgroups.makepath.assert_called_with(
            'memory', 'some_cgrp', 'memory.oom_control'
        )
        io.open.assert_called_with('mock_oom_control')
        treadmill.cgroups.set_value.assert_called_with(
            'memory', 'some_cgrp', 'cgroup.event_control',
            # '<eventfd_fd> <oom_control_fd>'
            '42 43'
        )
        # Should be returning the eventfd socket
        self.assertEqual(res, 42)

    @mock.patch('treadmill.cgroups._get_mountpoint', mock.Mock(set_spec=True))
    @mock.patch('os.rmdir', mock.Mock(set_spec=True))
    def test_delete_rec(self):
        """Tests recursive cgroup deletion.
        """
        # pylint: disable=W0212

        cgroups_dir = os.path.join(self.root, 'cgroups')
        treadmill.cgroups._get_mountpoint.return_value = cgroups_dir

        group = os.path.join('treadmill', 'apps', 'test1')
        # Create a directory and subdirs for the cgroup
        os.makedirs(os.path.join(cgroups_dir, group, 'foo', 'bar', 'baz'))

        cgutils.delete('cpu', group)

        os.rmdir.assert_has_calls([
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar/baz')),
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar')),
            mock.call(os.path.join(cgroups_dir, group, 'foo')),
            mock.call(os.path.join(cgroups_dir, group)),
        ])

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_bps_info(self):
        """Test reading of blkio throttle bps information.
        """
        data = self._blkio_throttle_bps
        treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.throttle.io_service_bytes')

        treadmill.cgroups.get_data.assert_called_with(
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

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_info_empty(self):
        """Test reading of blkio information with empty file.
        """
        data = self._blkio_bps_empty
        treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.io_service_bytes')
        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.io_service_bytes'
        )
        self.assertEqual(
            data,
            {}
        )

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_value_empty(self):
        """Test reading of blkio information with empty file.
        """
        data = self._blkio_sectors_empty
        treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_value('mycgrp',
                                       'blkio.sectors')
        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.sectors'
        )
        self.assertEqual(
            data,
            {}
        )

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_iops_info(self):
        """Test reading of blkio throttle iops information.
        """
        data = self._blkio_throttle_iops
        treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.throttle.io_serviced')

        treadmill.cgroups.get_data.assert_called_with(
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

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(side_effect=['0', '0', '', '1024', '512']))
    @mock.patch('treadmill.sysinfo.cpu_count',
                mock.Mock(return_value=4))
    def test_create_treadmill_cgroups(self):
        """Test the creation of core treadmill cgroups.
        """
        treadmill_core_cpu_shares = 10
        treadmill_apps_cpu_shares = 90
        treadmill_core_cpuset_cpus = '0-15'
        treadmill_app_cpuset_cpus = '1-15'
        treadmill_core_mem = 512
        treadmill_apps_mem = 256
        cgutils.create_treadmill_cgroups(treadmill_core_cpu_shares,
                                         treadmill_apps_cpu_shares,
                                         treadmill_core_cpuset_cpus,
                                         treadmill_app_cpuset_cpus,
                                         treadmill_core_mem,
                                         treadmill_apps_mem,
                                         'treadmill')

        calls = [mock.call('cpu', 'treadmill/core'),
                 mock.call('cpu', 'treadmill/apps'),
                 mock.call('cpuacct', 'treadmill/core'),
                 mock.call('cpuacct', 'treadmill/apps'),
                 mock.call('cpuset', 'treadmill/core'),
                 mock.call('cpuset', 'treadmill/apps'),
                 mock.call('memory', 'treadmill/core'),
                 mock.call('memory', 'treadmill/apps')]
        treadmill.cgroups.create.assert_has_calls(calls)
        calls = [mock.call('cpu', 'treadmill/core',
                           'cpu.shares', treadmill_core_cpu_shares),
                 mock.call('cpu', 'treadmill/apps',
                           'cpu.shares', treadmill_apps_cpu_shares),
                 mock.call('cpuset', 'treadmill/core',
                           'cpuset.mems', '0'),
                 mock.call('cpuset', 'treadmill/apps',
                           'cpuset.mems', '0'),
                 mock.call('cpuset', 'treadmill/core',
                           'cpuset.cpus', '0-15'),
                 mock.call('cpuset', 'treadmill/apps',
                           'cpuset.cpus', '1-15'),
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
        """Make sure we are setting hardlimits right.
        """
        cgutils.reset_memory_limit_in_bytes('treadmill')
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
        """Make sure we kill groups when we cannot lower their hardlimits.
        """
        treadmill.cgutils.set_memory_hardlimit.side_effect = \
            cgutils.TreadmillCgroupError('test')

        res = cgutils.reset_memory_limit_in_bytes('treadmill')

        self.assertEqual(res, ['a'])


if __name__ == '__main__':
    unittest.main()
