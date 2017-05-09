"""
Unit test for treadmill.cli.configure
"""

import importlib
import tempfile
import unittest

import click
import click.testing
import mock
import yaml

import treadmill


class RunTest(unittest.TestCase):
    """Mock test for treadmill.cli.run"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.cli = importlib.import_module('treadmill.cli.run').init()

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_nameonly(self):
        """Test cli.run no manifest."""
        result = self.runner.invoke(self.cli, ['--cell', 'xx', 'proid.app'])
        self.assertEquals(result.exit_code, 0)
        treadmill.restclient.post.assert_called_with(
            ['http://xxx:1234'],
            '/instance/proid.app?count=1',
            payload={}
        )

    @mock.patch('treadmill.restclient.post',
                mock.Mock(return_value=mock.MagicMock()))
    @mock.patch('treadmill.context.Context.cell_api',
                mock.Mock(return_value=['http://xxx:1234']))
    def test_run_withmanifest(self):
        """Test cli.run no manifest."""

        with tempfile.NamedTemporaryFile(delete=False) as f:

            manifest = {
                'memory': '1G',
                'disk': '1G',
                'cpu': '100%',
            }

            yaml.dump(manifest, stream=f)
            expected_payload = dict(manifest)
            result = self.runner.invoke(self.cli, [
                '--cell', 'xx', 'proid.app',
                '--manifest', f.name,
            ])
            self.assertEquals(result.exit_code, 0)
            treadmill.restclient.post.assert_called_with(
                ['http://xxx:1234'],
                '/instance/proid.app?count=1',
                payload=expected_payload
            )

            expected_payload['memory'] = '333M'
            result = self.runner.invoke(self.cli, [
                '--cell', 'xx', 'proid.app',
                '--memory', '333M',
                '--manifest', f.name,
            ])
            self.assertEquals(result.exit_code, 0)
            treadmill.restclient.post.assert_called_with(
                ['http://xxx:1234'],
                '/instance/proid.app?count=1',
                payload=expected_payload
            )


if __name__ == '__main__':
    unittest.main()
