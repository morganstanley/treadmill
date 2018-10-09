"""Unit test for treadmill.cli.configure
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import tempfile
import unittest

import click
import click.testing
import mock

import treadmill
from treadmill import plugin_manager
from treadmill import yamlwrapper as yaml


class RunTest(unittest.TestCase):
    """Mock test for treadmill.cli.run"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.cli = plugin_manager.load('treadmill.cli', 'run').init()

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_nameonly(self):
        """Test cli.run no manifest."""
        result = self.runner.invoke(self.cli, ['--cell', 'xx', 'proid.app'])
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload={}
        )

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_debug(self):
        """Test cli.run with debug option."""
        result = self.runner.invoke(
            self.cli, ['--cell', 'xx', 'proid.app', '--debug']
        )
        self.assertEqual(result.exit_code, 0)
        args, kwargs = treadmill.restclient.post.call_args
        _, url = args
        self.assertIn('debug=true', url)

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_debug_services(self):
        """Test cli.run with debug services option."""
        result = self.runner.invoke(
            self.cli, ['--cell', 'xx', 'proid.app', '--debug-services', 'test']
        )
        self.assertEqual(result.exit_code, 0)
        args, kwargs = treadmill.restclient.post.call_args
        _, url = args
        self.assertIn('debug_services=test', url)

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_normalparam(self):
        """Test cli.run service with normal parameters."""
        result = self.runner.invoke(
            self.cli,
            ['--cell', 'xx', 'proid.app', '--', '/dir/test.sh 1 2 3']
        )
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload={
                'services': [
                    {
                        'command': '/dir/test.sh 1 2 3',
                        'name': 'test.sh',
                        'restart': {'interval': 60, 'limit': 0}
                    }
                ],
                'disk': '100M',
                'cpu': '10%',
                'memory': '100M'
            }
        )

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_emptyparam(self):
        """Test cli.run service with empty parameter."""
        result = self.runner.invoke(
            self.cli,
            ['--cell', 'xx', 'proid.app', '--', '/dir/test.sh 1 \"\" 3']
        )
        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload={
                'services': [
                    {
                        'command': '/dir/test.sh 1 "" 3',
                        'name': 'test.sh',
                        'restart': {'interval': 60, 'limit': 0}
                    }
                ],
                'disk': '100M',
                'cpu': '10%',
                'memory': '100M'
            }
        )

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_withmanifest(self):
        """Test cli.run no manifest."""
        manifest = {
            'memory': '1G',
            'disk': '1G',
            'cpu': '100%',
        }

        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            yaml.dump(manifest, stream=f)

        result = self.runner.invoke(self.cli, [
            '--cell', 'xx', 'proid.app',
            '--manifest', f.name,
        ])

        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload=manifest
        )

        # Test manifest parameter override
        manifest['memory'] = '333M'

        result = self.runner.invoke(self.cli, [
            '--cell', 'xx', 'proid.app',
            '--memory', '333M',
            '--manifest', f.name,
        ])

        self.assertEqual(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload=manifest
        )


if __name__ == '__main__':
    unittest.main()
