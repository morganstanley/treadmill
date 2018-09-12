"""Unit test for treadmill.cli.logs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

from treadmill import plugin_manager
from treadmill import restclient
from treadmill.websocket import client as wsclient


# don't compain about protected member access
# pylint: disable=W0212
class LogsTest(unittest.TestCase):
    """Mock test for treadmill.cli.logs"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.log_mod = plugin_manager.load('treadmill.cli', 'logs')
        self.log_cli = self.log_mod.init()

    @mock.patch('treadmill.websocketutils.find_running_instance',
                mock.Mock(return_value={'host': 'host',
                                        'uniq': 'uniq'}))
    @mock.patch('treadmill.cli.logs._find_endpoints',
                mock.Mock(return_value=[{'host': 'host',
                                         'port': 1234}]))
    @mock.patch('treadmill.restclient.get',
                side_effect=restclient.NotFoundError('foobar'))
    def test_no_logfile_found(self, _):
        """Test the output if no log file can be found."""
        result = self.runner.invoke(self.log_cli,
                                    ['--cell', 'foo',
                                     'proid.app#123/running/service/foo'])

        # let's check that NotFoundError is handled
        self.assertEqual(str(result.exception).find('foobar'), -1)

    @mock.patch('treadmill.websocketutils.find_uniq_instance',
                side_effect=wsclient.WSConnectionError('foo'))
    def test_ws_connection_error(self, _):
        """Test that the websocket.client.WSConnectionError is handled."""
        result = self.runner.invoke(self.log_cli,
                                    ['--cell', 'foo',
                                     'proid.app#123/5FiY/service/zk2fs'])

        # let's check that WSConnectionError is handled ie. it cannot be found
        # in the result
        self.assertEqual(str(result.exception).find('foo'), -1)
        self.assertEqual(result.exit_code, 1)
        self.assertTrue('Cannot resolve websocket api' in
                        result.output)


if __name__ == '__main__':
    unittest.main()
