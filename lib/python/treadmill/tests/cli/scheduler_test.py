"""Report CLI tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click.testing
import mock
import requests

from treadmill import restclient
from treadmill import plugin_manager


class ReportTest(unittest.TestCase):
    """Test the scheduler CLI command."""

    def setUp(self):
        """Set up the CLI test."""
        self.runner = click.testing.CliRunner()
        self.scheduler = plugin_manager.load(
            'treadmill.cli',
            'scheduler'
        ).init()

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_servers_report(self):
        """Test behaviour and output of the servers report."""
        restclient.get.return_value.json.return_value = {
            'columns': [
                'name', 'location', 'partition',
                'traits', 'state', 'valid_until',
                'mem', 'cpu', 'disk',
                'mem_free', 'cpu_free', 'disk_free'
            ],
            'data': [
                [
                    'example.ms.com', 'foo/building:bar/rack:baz', '_default',
                    'sse', 'up', 1500000000,
                    1001, 2001, 3001,
                    1000, 2000, 3000
                ]
            ]
        }

        result = self.runner.invoke(
            self.scheduler, ['--cell', 'TEST', 'servers']
        )

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/servers'
        )

        self.assertIn('example.ms.com', result.output)
        self.assertIn('foo/building:bar/rack:baz', result.output)
        self.assertIn('_default', result.output)
        self.assertIn('sse', result.output)
        self.assertIn('up', result.output)
        self.assertIn('2017-07-14 02:40:00', result.output)
        self.assertIn('1001', result.output)
        self.assertIn('2001', result.output)
        self.assertIn('3001', result.output)
        self.assertIn('1000', result.output)
        self.assertIn('2000', result.output)
        self.assertIn('3000', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_allocs_report(self):
        """Test behaviour and output of the allocs report."""
        restclient.get.return_value.json.return_value = {
            'columns': [
                'partition', 'name',
                'mem', 'cpu', 'disk',
                'rank', 'rank_adj', 'traits', 'max_util'
            ],
            'data': [
                ['part1', '_default/proid', 1, 1, 1, 1, 1, 1, 1],
                [
                    'part1', 'tenant/proid',
                    1001, 1002, 1003,
                    99, 98, 'sse', 6
                ]
            ]
        }

        result = self.runner.invoke(
            self.scheduler, ['--cell', 'TEST', 'allocs']
        )

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/allocations'
        )

        self.assertNotIn('_default', result.output)
        self.assertIn('part1', result.output)
        self.assertIn('tenant/proid', result.output)
        self.assertIn('1001', result.output)
        self.assertIn('1002', result.output)
        self.assertIn('1003', result.output)
        self.assertIn('99', result.output)
        self.assertIn('98', result.output)
        self.assertIn('sse', result.output)
        self.assertIn('6', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_match_argument(self):
        """Test behaviour of the --match flag."""
        restclient.get.return_value.json.return_value = {
            'columns': ['name'],
            'data': [['foo']]
        }

        result = self.runner.invoke(self.scheduler, [
            '--cell', 'TEST', 'allocs', '--match', '.*'
        ])

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/allocations?match=.%2A'
        )

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_partition_argument(self):
        """Test behaviour of the --partition flag."""
        restclient.get.return_value.json.return_value = {
            'columns': ['name'],
            'data': [['foo']]
        }

        result = self.runner.invoke(self.scheduler, [
            '--cell', 'TEST', 'allocs', '--partition', '.*'
        ])

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/allocations?partition=.%2A'
        )

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_apps_report_condensed(self):
        """Test behaviour and output of the condensed apps report."""
        restclient.get.return_value.json.return_value = {
            'columns': [
                'instance', 'allocation', 'rank', 'affinity', 'partition',
                'identity_group', 'identity',
                'order', 'lease', 'expires', 'data_retention',
                'pending', 'server', 'util',
                'mem', 'cpu', 'disk'
            ],
            'data': [
                [
                    'app.foo', 'tenant/foo', 99, 'affin.foo', '_default',
                    'ident.foo', 101,
                    123, 120, 1500000000, 300,
                    0, 'example.ms.com', 0.05,
                    1001, 1002, 1003
                ]
            ]
        }

        result = self.runner.invoke(
            self.scheduler, ['--cell', 'TEST', 'apps']
        )

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/apps'
        )

        self.assertIn('app.foo', result.output)
        self.assertIn('tenant/foo', result.output)
        self.assertNotIn('99', result.output)  # rank
        self.assertNotIn('affin.foo', result.output)
        self.assertIn('_default', result.output)
        self.assertNotIn('ident.foo', result.output)
        self.assertNotIn('101', result.output)  # identity
        self.assertNotIn('123', result.output)  # order
        self.assertNotIn('0 days 00:02:00', result.output)  # lease
        self.assertNotIn('2017-07-14 02:40:00', result.output)  # expires
        self.assertNotIn('0 days 00:05:00', result.output)  # data_retention
        self.assertIn('example.ms.com', result.output)
        self.assertNotIn('0.05', result.output)  # util
        self.assertIn('1001', result.output)
        self.assertIn('1002', result.output)
        self.assertIn('1003', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_apps_report_full(self):
        """Test behaviour and output of the full apps report."""
        restclient.get.return_value.json.return_value = {
            'columns': [
                'instance', 'allocation', 'rank', 'affinity', 'partition',
                'identity_group', 'identity',
                'order', 'lease', 'expires', 'data_retention',
                'pending', 'server', 'util',
                'mem', 'cpu', 'disk'
            ],
            'data': [
                [
                    'app.foo', 'tenant/foo', 99, 'affin.foo', '_default',
                    'ident.foo', 101,
                    123, 120, 1500000000, 300,
                    0, 'example.ms.com', 0.05,
                    1001, 1002, 1003
                ]
            ]
        }

        result = self.runner.invoke(
            self.scheduler, ['--cell', 'TEST', 'apps', '--full']
        )

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'],
            '/scheduler/apps'
        )

        self.assertIn('app.foo', result.output)
        self.assertIn('tenant/foo', result.output)
        self.assertIn('99', result.output)  # rank
        self.assertIn('affin.foo', result.output)
        self.assertIn('_default', result.output)
        self.assertIn('ident.foo', result.output)
        self.assertIn('101', result.output)  # identity
        self.assertIn('123', result.output)  # order
        self.assertIn('0 days 00:02:00', result.output)  # lease
        self.assertIn('2017-07-14 02:40:00', result.output)  # expires
        self.assertIn('0 days 00:05:00', result.output)  # data_retention
        self.assertIn('example.ms.com', result.output)
        self.assertIn('0.05', result.output)  # util
        self.assertIn('1001', result.output)
        self.assertIn('1002', result.output)
        self.assertIn('1003', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://example.com']))
    def test_explain(self):
        """Test behaviour and output of the 'explain' subverb."""
        restclient.get.return_value.json.return_value = {
            'columns': [
                'partition', 'traits', 'affinity', 'state', 'lifetime',
                'memory', 'cpu', 'disk', 'name'
            ],
            'data': [
                [
                    'True', 'True', 'True', 'False', 'True', 'False', 'True',
                    'False', 'host_1.ms.com'
                ], [
                    'True', 'True', 'True', 'True', 'True', 'False', 'True',
                    'False', 'host_2.ms.com'
                ]
            ]
        }

        result = self.runner.invoke(
            self.scheduler, ['--cell', 'TEST', 'explain', 'proid.app#123']
        )

        self.assertEqual(result.exit_code, 0)
        restclient.get.assert_called_with(
            ['http://example.com'], '/scheduler/explain/proid.app%23123'
        )

        self.assertIn('host_1.ms.com', result.output)
        self.assertIn('host_2.ms.com', result.output)
        self.assertIn('X', result.output)

        explain_mod = plugin_manager.load(
            'treadmill.cli.scheduler',
            'explain'
        )
        # W0212(protected-access)
        # pylint: disable=W0212
        auto_handled_excepts = [ex[0] for ex in explain_mod._EXCEPTIONS]
        self.assertNotIn(restclient.AlreadyExistsError, auto_handled_excepts)


if __name__ == '__main__':
    unittest.main()
