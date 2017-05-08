"""
Unit test for treadmill.cli.configure
"""

import importlib
import unittest
import re

import click
import click.testing
import mock
import requests

from treadmill import restclient


class ConfigureTest(unittest.TestCase):
    """Mock test for treadmill.cli.configure"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.configure').init()

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_configure_get(self):
        """Test cli.configure: get"""
        restclient.get.return_value.json.return_value = {
            '_id': 'proid.app',
            'memory': '128M',
            'cpu': '5%',
            'disk': '100M',
            'identity_group': 'ident-group',
        }

        result = self.runner.invoke(self.configure_cli,
                                    ['proid.app'])
        self.assertEquals(result.exit_code, 0)
        self.assertIn('proid.app', result.output)
        self.assertIn('128M', result.output)
        self.assertIn('5%', result.output)
        self.assertIn('100M', result.output)
        self.assertIn('ident-group', result.output)

        self.assertTrue(
            re.search(r'^tickets\s+:\s+-', result.output, re.MULTILINE)
        )

        self.assertNotIn('/bin/sleep', result.output)

    @mock.patch('treadmill.restclient.get', mock.MagicMock())
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_configure_list(self):
        """Test cli.configure: list"""
        restclient.get.return_value.json.return_value = [
            {'_id': 'proid.app',
             'memory': '128M',
             'cpu': '5%',
             'disk': '100M',
             'identity_group': 'ident-group'},
            {'_id': 'proid.app2',
             'memory': '128M',
             'cpu': '50%',
             'disk': '200M',
             'identity_group': 'ident-group2'},
        ]

        result = self.runner.invoke(self.configure_cli, [])

        self.assertEquals(result.exit_code, 0)

        self.assertTrue(
            re.search(r'^proid.app\s+', result.output, re.MULTILINE)
        )
        self.assertTrue(
            re.search(r'^proid.app2\s+', result.output, re.MULTILINE)
        )

        self.assertNotIn('ident-group', result.output)


if __name__ == '__main__':
    unittest.main()
