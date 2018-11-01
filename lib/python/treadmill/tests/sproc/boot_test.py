"""Unit test for treadmill.sproc.boot
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.sproc import boot


class BootTest(unittest.TestCase):
    """Test Sproc boot module
    """

    @mock.patch('treadmill.sysinfo.cpu_count',
                mock.Mock(return_value=6))
    def test__total_cpu_cores(self):
        """get correct cpu core indices out ot cpuset.cpus string
        """
        # pylint: disable=protected-access
        total = boot._total_cpu_cores('1,2')
        self.assertEqual(total, set([1, 2]))

        total = boot._total_cpu_cores('0-2')
        self.assertEqual(total, set([0, 1, 2]))

        total = boot._total_cpu_cores('2-')
        self.assertEqual(total, set([2, 3, 4, 5]))

        total = boot._total_cpu_cores('0,3-5')
        self.assertEqual(total, set([0, 3, 4, 5]))

        total = boot._total_cpu_cores(None)
        self.assertEqual(total, set([0, 1, 2, 3, 4, 5]))

    @mock.patch('treadmill.sysinfo.cpu_count',
                mock.Mock(return_value=4))
    def test__parse_cpuset_cpus(self):
        """parse cpuset cores value for cpuset.cpus
        """
        # pylint: disable=protected-access
        output = boot._parse_cpuset_cpus('-')
        self.assertIsNone(output)

        output = boot._parse_cpuset_cpus('2,3')
        self.assertEqual(output, '2,3')

        output = boot._parse_cpuset_cpus('1-')
        self.assertEqual(output, '1-3')

        output = boot._parse_cpuset_cpus('0,2-3')
        self.assertEqual(output, '0,2-3')


if __name__ == '__main__':
    unittest.main()
