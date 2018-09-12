"""Unit test for App DNS
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


class AppDNSTest(unittest.TestCase):
    """Mock test for App DNS"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.app_dns = plugin_manager.load('treadmill.cli', 'app-dns').init()

    @mock.patch('treadmill.restclient.call',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_app_dns_configure_get(self):
        """Test cli.app-dns.configure: get"""
        restclient.get.return_value.json.return_value = {
            '_id': 'proid.app_dns1',
            'cells': ['foo-cell'],
            'pattern': 'proid.app_dns*',
            'alias': 'foo-alias',
        }

        result = self.runner.invoke(self.app_dns,
                                    ['configure', 'proid.app_dns1'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app_dns1', result.output)
        self.assertIn('foo-alias', result.output)

    @mock.patch('treadmill.restclient.call',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.restclient.get', mock.MagicMock())
    @mock.patch('treadmill.restclient.post', mock.Mock())
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_app_dns_configure_create(self):
        """Test cli.app-dns.configure: create"""
        restclient.get.side_effect = restclient.NotFoundError('')

        self.runner.invoke(
            self.app_dns, ['configure', 'proid.app_dns1',
                           '--pattern', 'proid.xxx']
        )

        restclient.post.assert_called_with(
            mock.ANY, '/app-dns/proid.app_dns1', {
                'pattern': 'proid.xxx'})

    @mock.patch('treadmill.restclient.call',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.restclient.get', mock.Mock())
    @mock.patch('treadmill.restclient.put', mock.Mock())
    @mock.patch('treadmill.restclient.post', mock.Mock())
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_app_dns_configure_update(self):
        """Test cli.app-dns.configure: update"""
        restclient.get.return_value.json.return_value = {
            '_id': 'proid.app_dns1',
            'cells': ['foo-cell'],
            'pattern': 'proid.yyy',
        }
        restclient.post.side_effect = restclient.AlreadyExistsError('')

        self.runner.invoke(
            self.app_dns, ['configure', 'proid.app_dns1',
                           '--pattern', 'proid.xxx']
        )

        restclient.put.assert_called_with(
            mock.ANY, '/app-dns/proid.app_dns1', {
                'pattern': 'proid.xxx'})

    @mock.patch('treadmill.restclient.call',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.restclient.get', mock.MagicMock())
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_app_dns_list(self):
        """Test cli.app-dns.list"""
        restclient.get.return_value.json.return_value = [
            {'_id': 'proid.app_dns1',
             'cells': ['foo-cell'],
             'pattern': 'proid.app_dns*'},
            {'_id': 'proid.app_dns2',
             'cells': ['foo-cell'],
             'pattern': 'proid.app_dns*',
             'alias': 'proid.foo'}
        ]

        result = self.runner.invoke(self.app_dns, ['list'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app_dns1', result.output)
        self.assertIn('proid.app_dns2', result.output)
        self.assertIn('proid.foo', result.output)


if __name__ == '__main__':
    unittest.main()
