"""
Unit test for treadmill.cli.show
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock
import requests

from treadmill import restclient
from treadmill import plugin_manager


class ShowTest(unittest.TestCase):
    """Mock test for treadmill.cli.show"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.cli = plugin_manager.load('treadmill.cli', 'show').init()

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.state_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_show_endpoints_no_endpoint(self):
        """Test cli.show.endpoints with no endpoint provided in CLI"""
        restclient.get.return_value.json.return_value = [
            {'name': 'proid.app#12345',
             'endpoint': 'http',
             'proto': 'tcp',
             'host': 'foo.com',
             'port': '1245'},
            {'name': 'proid.app#12345',
             'endpoint': 'ssh',
             'proto': 'tcp',
             'host': 'foo.com',
             'port': '1246'},
        ]

        result = self.runner.invoke(
            self.cli,
            ['--cell', 'test', 'endpoints', 'proid.app'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app#12345', result.output)
        self.assertIn('http', result.output)
        self.assertIn('tcp', result.output)
        self.assertIn('foo.com', result.output)
        self.assertIn('1245', result.output)
        self.assertIn('1246', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.state_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_show_endpoints_w_endpoint(self):
        """Test cli.show.endpoints with endpoint provided in CLI"""
        restclient.get.return_value.json.return_value = [
            {'name': 'proid.app#12345',
             'endpoint': 'http',
             'proto': 'tcp',
             'host': 'foo.com',
             'port': '1245'},
        ]

        result = self.runner.invoke(
            self.cli,
            ['--cell', 'test', 'endpoints', 'proid.app'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app#12345', result.output)
        self.assertIn('http', result.output)
        self.assertIn('tcp', result.output)
        self.assertIn('foo.com', result.output)
        self.assertIn('1245', result.output)

        self.assertNotIn('1246', result.output)
        self.assertNotIn('ssh', result.output)


if __name__ == '__main__':
    unittest.main()
