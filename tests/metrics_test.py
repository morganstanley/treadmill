"""Test for treadmill.metrics."""

import unittest
from collections import namedtuple

import mock

from treadmill import metrics
from treadmill import sysinfo

STATINFO = """cache 0
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

    @mock.patch('treadmill.cgutils.cgrp_meminfo',
                mock.Mock(return_value=(10, 12, 13)))
    @mock.patch('treadmill.cgutils.pids_in_cgroup',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(return_value=STATINFO))
    @mock.patch('time.time', mock.Mock(return_value=1234))
    def test_read_memory_stats(self):
        """Tests updating memory stats from cgroups."""
        self.assertEqual(metrics.read_memory_stats('treadmill/apps/appname'),
                         (10, 12, 13))

    @mock.patch('treadmill.cgutils.cpu_usage',
                mock.Mock(return_value=100))
    @mock.patch('treadmill.cgutils.stat',
                mock.Mock(return_value=namedtuple('stat', ['st_mtime'])(0)))
    @mock.patch('treadmill.cgutils.reset_cpu_usage',
                mock.Mock())
    @mock.patch('treadmill.cgroups.get_cpu_shares',
                mock.Mock(return_value=10))
    @mock.patch('treadmill.sysinfo.total_bogomips',
                mock.Mock(return_value=100))
    @mock.patch('treadmill.sysinfo.cpu_count',
                mock.Mock(return_value=1))
    @mock.patch('treadmill.cgutils.get_cpu_ratio',
                mock.Mock(return_value=.5))
    @mock.patch('time.time', mock.Mock(return_value=10))
    def test_update_cpu_metrics(self):
        """Tests updating cpu stats from cgroups."""
        cpumetrics = metrics.read_cpu_stats('treadmill/apps/appname')

        cpu_usage = 100
        cpu_ratio = .5
        time_delta = 10
        cpu_count = 1
        cpu_shares = 10
        total_bogomips = 100

        requested_ratio = cpu_ratio * 100
        usage_ratio = ((cpu_usage * total_bogomips) /
                       (time_delta * cpu_shares) / cpu_count)
        usage = ((cpu_usage * total_bogomips) /
                 (time_delta * sysinfo.BMIPS_PER_CPU) /
                 cpu_count * 100)

        self.assertEqual(
            (usage, requested_ratio, usage_ratio),
            cpumetrics
        )

    @mock.patch('builtins.open',
                mock.mock_open(read_data='1.0 2.0 2.5 12/123 12345\n'))
    @mock.patch('time.time', mock.Mock(return_value=10))
    def test_read_load(self):
        """Tests reading loadavg."""
        self.assertEqual(('1.0', '2.0'), metrics.read_load())


if __name__ == '__main__':
    unittest.main()
