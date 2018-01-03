"""Unit test for treadmill.cli.admin.logs."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

from treadmill import context
from treadmill import plugin_manager
from treadmill import restclient


@unittest.skip('CLI interface broken (always returns -1)')
class AdminLogsTest(unittest.TestCase):
    """Mock test for treadmill.cli.admin.logs"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.log_mod = plugin_manager.load('treadmill.cli.admin', 'logs')
        self.log_cli = self.log_mod.init()
        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'
        context.GLOBAL.zk = mock.Mock()

    @mock.patch('treadmill.restclient.get', mock.Mock())
    def test_logs_style1(self):
        """Test treadmill admin logs"""
        context.GLOBAL.zk.conn.get_children.return_value = [
            'test_host#1:tcp:nodeinfo',
            'mock_host#1:tcp:nodeinfo'
        ]
        context.GLOBAL.zk.conn.get.return_value = (
            'test_host:12345',
            ''
        )
        res = self.runner.invoke(
            self.log_cli,
            [
                '--cell', 'test_cell',
                'proid.app#123/uniqid/service/foo',
                '--host', 'test_host'
            ]
        )
        self.assertEqual(res.exit_code, 0)
        restclient.get.assert_called_with(
            'http://test_host:12345',
            '/local-app/proid.app%23123/uniqid/service/foo'
        )

    @mock.patch('treadmill.restclient.get', mock.Mock())
    def test_logs_style2(self):
        """Test treadmill admin logs"""
        context.GLOBAL.zk.conn.get_children.return_value = [
            'test_host#1:tcp:nodeinfo',
            'mock_host#1:tcp:nodeinfo'
        ]
        context.GLOBAL.zk.conn.get.return_value = (
            'test_host:12345',
            ''
        )
        res = self.runner.invoke(
            self.log_cli,
            [
                '--cell', 'test_cell',
                'proid.app#123',
                '--host', 'test_host',
                '--uniq', 'uniqid',
                '--service', 'foo'
            ]
        )
        self.assertEqual(res.exit_code, 0)
        restclient.get.assert_called_with(
            'http://test_host:12345',
            '/local-app/proid.app%23123/uniqid/service/foo'
        )


if __name__ == '__main__':
    unittest.main()
