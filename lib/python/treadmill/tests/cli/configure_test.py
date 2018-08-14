"""Unit test for treadmill.cli.configure
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import re
import tempfile

import click
import click.testing
import mock
import requests

from treadmill import fs
from treadmill import restclient
from treadmill import plugin_manager
from treadmill import yamlwrapper as yaml


class ConfigureTest(unittest.TestCase):
    """Mock test for treadmill.cli.configure"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.configure = plugin_manager.load(
            'treadmill.cli', 'configure').init()

        with tempfile.NamedTemporaryFile(delete=False) as f:
            yaml.dump({
                'memory': '128M',
                'cpu': '5%',
                'disk': '100M',
                'identity_group': 'ident-group',
            }, f, encoding='utf-8')

        self.manifest = f.name

    def tearDown(self):
        fs.rm_safe(self.manifest)

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

        result = self.runner.invoke(self.configure,
                                    ['proid.app'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app', result.output)
        self.assertIn('128M', result.output)
        self.assertIn('5%', result.output)
        self.assertIn('100M', result.output)
        self.assertIn('ident-group', result.output)

        self.assertTrue(
            re.search(r'^tickets\s+:\s+-', result.output, re.MULTILINE)
        )

        self.assertNotIn('/bin/sleep', result.output)

    @mock.patch('treadmill.restclient.get',
                mock.Mock(side_effect=restclient.NotFoundError))
    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_configure_create(self):
        """Test cli.configure: create"""
        restclient.post.return_value.json.return_value = {
            '_id': 'proid.app',
            'memory': '128M',
            'cpu': '5%',
            'disk': '100M',
            'identity_group': 'ident-group',
        }

        result = self.runner.invoke(
            self.configure,
            ['proid.app', '--manifest', self.manifest]
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app', result.output)
        self.assertIn('128M', result.output)
        self.assertIn('5%', result.output)
        self.assertIn('100M', result.output)
        self.assertIn('ident-group', result.output)

        restclient.post.assert_called_once_with(
            ['http://xxx:1234'],
            '/app/proid.app',
            payload={
                'cpu': '5%',
                'disk': '100M',
                'memory': '128M',
                'identity_group': 'ident-group',
            }
        )

    @mock.patch('treadmill.restclient.get',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.restclient.put',
                mock.Mock(return_value=mock.MagicMock(requests.Response)))
    @mock.patch('treadmill.context.Context.admin_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_configure_update(self):
        """Test cli.configure: update"""
        restclient.get.return_value.json.return_value = {
            '_id': 'proid.app',
            'memory': '100M',
            'cpu': '5%',
            'disk': '100M',
            'identity_group': 'ident-group',
        }
        restclient.put.return_value.json.return_value = {
            '_id': 'proid.app',
            'memory': '128M',
            'cpu': '5%',
            'disk': '100M',
            'identity_group': 'ident-group',
        }

        result = self.runner.invoke(
            self.configure,
            ['proid.app', '--manifest', self.manifest]
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn('proid.app', result.output)
        self.assertIn('128M', result.output)
        self.assertIn('5%', result.output)
        self.assertIn('100M', result.output)
        self.assertIn('ident-group', result.output)

        restclient.put.assert_called_once_with(
            ['http://xxx:1234'],
            '/app/proid.app',
            payload={
                'cpu': '5%',
                'disk': '100M',
                'memory': '128M',
                'identity_group': 'ident-group',
            }
        )

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

        result = self.runner.invoke(self.configure, ['--match', 'proid'])

        self.assertEqual(result.exit_code, 0)

        self.assertTrue(
            re.search(r'^proid.app\s+', result.output, re.MULTILINE)
        )
        self.assertTrue(
            re.search(r'^proid.app2\s+', result.output, re.MULTILINE)
        )

        self.assertNotIn('ident-group', result.output)


if __name__ == '__main__':
    unittest.main()
