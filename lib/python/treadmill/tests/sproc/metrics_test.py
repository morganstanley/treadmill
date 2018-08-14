"""Unit test for treadmill.sproc.metrics.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

from collections import namedtuple

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import appenv
from treadmill.sproc import metrics


class MetricsTest(unittest.TestCase):
    """Test treadmill.sproc.metrics"""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.sysinfo.mem_info',
                mock.Mock(return_value=namedtuple('memory', 'total')(16000)))
    @mock.patch('treadmill.sysinfo.total_bogomips', mock.Mock(return_value=10))
    @mock.patch('treadmill.sysinfo.available_cpu_count',
                mock.Mock(return_value=4))
    def test_update_core_rrds(self):
        """Test update core rrds"""
        data = {
            'apps': {'timestamp': 1},
            'core': {'timestamp': 2},
            'treadmill': {
                'timestamp': 3,
                'memory.usage_in_bytes': 10,
                'memory.soft_limit_in_bytes': 10,
                'memory.limit_in_bytes': 10,
                'cpuacct.usage': 3000000000,
                'cpu.shares': 1024,
                'blkio.throttle.io_service_bytes': {},
                'blkio.throttle.io_serviced': {},
                'fs.used_bytes': 10,
            },
        }
        rrdclient = mock.Mock()
        # pylint: disable=W0212
        metrics._update_core_rrds(data, self.root, rrdclient, 5, '10:0')
        rrdclient.create.assert_has_calls(
            [
                mock.call('{}/treadmill.core.rrd'.format(self.root), 5, 10),
                mock.call('{}/treadmill.apps.rrd'.format(self.root), 5, 10),
                mock.call('{}/treadmill.system.rrd'.format(self.root), 5, 10),
            ],
            any_order=True
        )

        metrics_data = {
            'hardmem': 10, 'softmem': 10, 'blk_write_iops': 0, 'memusage': 10,
            'fs_used_bytes': 10, 'blk_read_bps': 0,
            'cpuusage_ratio': 0.000244140625,
            'cpuusage': 0.00625,
            'blk_read_iops': 0, 'cputotal': 3000000000, 'blk_write_bps': 0,
            'timestamp': 3
        }
        rrdclient.update.assert_has_calls([
            mock.call(
                '{}/treadmill.system.rrd'.format(self.root), metrics_data,
                metrics_time=3
            )
        ])

    @mock.patch('treadmill.sysinfo.mem_info',
                mock.Mock(return_value=namedtuple('memory', 'total')(16000)))
    @mock.patch('treadmill.sysinfo.total_bogomips', mock.Mock(return_value=10))
    @mock.patch('treadmill.sysinfo.available_cpu_count',
                mock.Mock(return_value=4))
    @mock.patch('treadmill.services._base_service.ResourceService.get',
                mock.Mock(return_value={'dev_major': 3, 'dev_minor': 0}))
    def test_update_app_rrds(self):
        """Test update container rrds"""
        data = {
            'foo.bar-00001-KKmc7hBHskLWh': {'timestamp': 1},
            'foo.bar-00002-KKmc7hBHskLWj': {
                'timestamp': 3,
                'memory.usage_in_bytes': 10,
                'memory.soft_limit_in_bytes': 10,
                'memory.limit_in_bytes': 10,
                'cpuacct.usage': 3000000000,
                'cpu.shares': 1024,
                'blkio.throttle.io_service_bytes': {
                    '3:0': {'Read': 5, 'Write': 3}
                },
                'blkio.throttle.io_serviced': {
                    '3:0': {'Read': 5, 'Write': 3}
                },
                'fs.used_bytes': 10,
            },
        }
        rrdclient = mock.Mock()
        tm_env = appenv.AppEnvironment(self.root)
        # pylint: disable=W0212
        metrics._update_app_rrds(data, self.root, rrdclient, 5, tm_env)
        rrdclient.create.assert_has_calls(
            [
                mock.call(
                    '{}/foo.bar-00002-KKmc7hBHskLWj.rrd'.format(self.root),
                    5, 10
                ),
                mock.call(
                    '{}/foo.bar-00001-KKmc7hBHskLWh.rrd'.format(self.root),
                    5, 10
                ),
            ],
            any_order=True
        )

        metrics_data = {
            'hardmem': 10, 'softmem': 10, 'blk_write_iops': 3, 'memusage': 10,
            'fs_used_bytes': 10, 'blk_read_bps': 5,
            'cpuusage_ratio': 0.000244140625, 'cpuusage': 0.00625,
            'blk_read_iops': 5, 'cputotal': 3000000000, 'blk_write_bps': 3,
            'timestamp': 3,
        }
        rrdclient.update.assert_has_calls(
            [
                mock.call(
                    '{}/foo.bar-00002-KKmc7hBHskLWj.rrd'.format(self.root),
                    metrics_data,
                    metrics_time=3
                )
            ]
        )


if __name__ == '__main__':
    unittest.main()
