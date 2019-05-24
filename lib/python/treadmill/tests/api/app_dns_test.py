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
             'alias': None, 'scope': None, 'identity-group': None}
        )
        # TODO
        # self.assertEqual(app_dns._dns2group(app_dns._group2dns(group)),
        #                  group)

        group['data'] = ['alias=foo', 'scope=region', 'identity-group=bar']
        self.assertEqual(
            app_dns._group2dns(group),
            {'pattern': 'xxx.yyy', 'cells': ['cell1'],
             'alias': 'foo', 'scope': 'region', 'identity-group': 'bar'}
        )
        # TODO
        # self.assertEqual(app_dns._dns2group(app_dns._group2dns(group)),
        #                  group)

    def test_dns2group(self):
        """Tests app-dns to app-group conversion."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212

        dns = {'pattern': 'xxx.yyy*', 'alias': 'x.alias', 'scope': 'cell'}
        self.assertEqual(
            app_dns._dns2group(dns), {
                'pattern': 'xxx.yyy*',
                'data': ['alias=x.alias', 'scope=cell'],
                'group-type': 'dns'
            })

        dns = {
            'pattern': 'xxx.yyy*',
            'cells': ['cell1'],
            'alias': 'x.alias',
            'scope': 'cell',
            'identity-group': 'x.id-group',
            'endpoints': ['http']
        }
        self.assertEqual(
            app_dns._dns2group(dns), {
                'cells': ['cell1'],
                'data': ['alias=x.alias', 'scope=cell',
                         'identity-group=x.id-group'],
                'endpoints': ['http'],
                'group-type': 'dns',
                'pattern': 'xxx.yyy*'
            })


if __name__ == '__main__':
    unittest.main()
