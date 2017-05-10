"""Unit test for treadmill.cli.logs."""

import importlib
import unittest

import click
import click.testing
import mock


# don't compain about protected member access
# pylint: disable=W0212
class LogsTest(unittest.TestCase):
    """Mock test for treadmill.cli.logs"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.log_mod = importlib.import_module('treadmill.cli.logs')
        self.log_cli = self.log_mod.init()

    @mock.patch('treadmill.discovery.iterator', mock.Mock(return_value=[]))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.cli.logs._get_nodeinfo_api',
                mock.Mock(return_value='http://...'))
    def test_logs(self):
        """Test the logs() command handler."""
        result = self.runner.invoke(
            self.log_cli, ['--host', 'ivapp1126006.devin3.ms.com', '--cell',
                           'foo', 'treadmld.cellapi/0000000469/sys/register'])

        self.assertEqual(result.exit_code, -1)


if __name__ == '__main__':
    unittest.main()
