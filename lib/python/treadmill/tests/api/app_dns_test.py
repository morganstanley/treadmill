"""Unit test for treadmill.api.app_dns.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.api import app_dns


class AppDnsTest(unittest.TestCase):
    """Test for app_dns."""

    def test_group2dns(self):
        """Tests group to dns conversion."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212

        group = {
            'group-type': 'dns',
            'pattern': 'xxx.yyy',
            'cells': ['cell1'],
            'data': {}
        }

        self.assertEqual(
            app_dns._group2dns(group),
            {'pattern': 'xxx.yyy', 'cells': ['cell1'],
             'alias': None, 'scope': None}
        )

        group['data'] = ['alias=foo', 'scope=region']
        self.assertEqual(
            app_dns._group2dns(group),
            {'pattern': 'xxx.yyy', 'cells': ['cell1'],
             'alias': 'foo', 'scope': 'region'}
        )


if __name__ == '__main__':
    unittest.main()
