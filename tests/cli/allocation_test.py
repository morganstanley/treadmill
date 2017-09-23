"""Unit test for treadmill.cli.allocation
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

import treadmill
from treadmill import plugin_manager


class AllocationTest(unittest.TestCase):
    """Mock test for treadmill.cli.allocation"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.alloc_cli = plugin_manager.load('treadmill.cli',
                                             'allocation').init()

    @mock.patch('treadmill.restclient.delete',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_allocation_delete(self):
        """Test cli.allocation: delete"""
        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/tenant/tent'
        )

        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent/dev'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/allocation/tent/dev'
        )

        result = self.runner.invoke(self.alloc_cli,
                                    ['delete', 'tent/dev/rr'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.delete.assert_called_with(
            ['http://xxx:1234'],
            '/allocation/tent/dev/reservation/rr'
        )


if __name__ == '__main__':
    unittest.main()
