"""Test for treadmill.metrics.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import metrics

_CPUACCT_STATINFO = """user 18335260
system 30990072"""

_CPU_STATINFO = """nr_periods 0
nr_throttled 0
throttled_time 0"""

_CPU_SHARE = '1024'

_MEM_STATINFO = """cache 0
rss 0
mapped_file 0
pgpgin 0
pgpgout 0
swap 0
inactive_anon 0
active_anon 0
inactive_file 0
active_file 0
unevictable 0
hierarchical_memory_limit 0
hierarchical_memsw_limit 0
total_cache 0
total_rss 0
total_mapped_file 0
total_pgpgin 0
total_pgpgout 0
total_swap 0
total_inactive_anon 0
total_active_anon 0
total_inactive_file 0
total_active_file 0
total_unevictable 0"""


class MetricsTest(unittest.TestCase):
    """Tests for teadmill.metrics."""

    @mock.patch('treadmill.metrics.cgrp_meminfo',
                mock.Mock(return_value={
                    'memory.failcnt': 2,
                    'memory.limit_in_bytes': 2,
                    'memory.max_usage_in_bytes': 2,
                    'memory.memsw.failcnt': 2,
                    'memory.memsw.limit_in_bytes': 2,
                }))
    @mock.patch('treadmill.cgutils.pids_in_cgroup',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(return_value=_MEM_STATINFO))
    def test_read_memory_stats(self):
        """Tests updating memory stats from cgroups."""
        self.assertEqual(
            metrics.read_memory_stats('treadmill/apps/appname'),
            {
                'memory.failcnt': 2,
                'memory.limit_in_bytes': 2,
                'memory.max_usage_in_bytes': 2,
                'memory.memsw.failcnt': 2,
                'memory.memsw.limit_in_bytes': 2,
                'memory.stat': {
                    'active_anon': 0,
                    'active_file': 0,
                    'cache': 0,
                    'hierarchical_memory_limit': 0,
                    'hierarchical_memsw_limit': 0,
                    'inactive_anon': 0,
                    'inactive_file': 0,
                    'mapped_file': 0,
                    'pgpgin': 0,
                    'pgpgout': 0,
                    'rss': 0,
                    'swap': 0,
                    'total_active_anon': 0,
                    'total_active_file': 0,
                    'total_cache': 0,
                    'total_inactive_anon': 0,
                    'total_inactive_file': 0,
                    'total_mapped_file': 0,
                    'total_pgpgin': 0,
                    'total_pgpgout': 0,
                    'total_rss': 0,
                    'total_swap': 0,
                    'total_unevictable': 0,
                    'unevictable': 0
                }
            }
        )

    @mock.patch('treadmill.cgutils.cpu_usage',
                mock.Mock(return_value=100))
    @mock.patch('treadmill.cgutils.per_cpu_usage',
                mock.Mock(return_value=[50, 50]))
    @mock.patch('treadmill.cgroups.get_data',
                mock.Mock(side_effect=[
                    _CPUACCT_STATINFO, _CPU_STATINFO, _CPU_SHARE
                ]))
    def test_read_cpu_metrics(self):
        """Tests updating cpu stats from cgroups."""
        cpumetrics = metrics.read_cpu_stats('treadmill/apps/appname')

        self.assertEqual(
            cpumetrics,
            {'cpu.stat': {'nr_periods': 0, 'nr_throttled': 0,
                          'throttled_time': 0},
             'cpuacct.stat': {'system': 309900720000000,
                              'user': 183352600000000},
             'cpuacct.usage': 100,
             'cpu.shares': 1024,
             'cpuacct.usage_percpu': [50, 50]}
        )

    @mock.patch('io.open',
                mock.mock_open(read_data='1.0 2.0 2.5 12/123 12345\n'))
    @mock.patch('time.time', mock.Mock(return_value=10))
    def test_read_load(self):
        """Tests reading loadavg."""
        self.assertEqual(('1.0', '2.0'), metrics.read_load())

    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(return_value=2))
    def test_cgrp_meminfo(self):
        """Test the grabbing of cgrp limits"""
        rv = metrics.cgrp_meminfo('foo')
        self.assertEqual(
            rv,
            {'memory.failcnt': 2,
             'memory.limit_in_bytes': 2,
             'memory.max_usage_in_bytes': 2,
             'memory.memsw.failcnt': 2,
             'memory.memsw.limit_in_bytes': 2,
             'memory.memsw.max_usage_in_bytes': 2,
             'memory.memsw.usage_in_bytes': 2,
             'memory.soft_limit_in_bytes': 2,
             'memory.usage_in_bytes': 2})

    @mock.patch('treadmill.fs.linux.blk_fs_info',
                mock.Mock(return_value={'block count': '2000',
                                        'free blocks': '1000',
                                        'block size': '1024'}))
    def test_get_fs_usage(self):
        """Test the fs usage compute logic."""
        self.assertEqual(
            metrics.get_fs_usage('/dev/treadmill/<uniq>'),
            {'fs.used_bytes': 1024000})

        self.assertEqual(metrics.get_fs_usage(None), {})

    def test_calc_fs_usage(self):
        """Test the fs usage compute logic."""
        self.assertEqual(metrics.calc_fs_usage({}), 0)


if __name__ == '__main__':
    unittest.main()
