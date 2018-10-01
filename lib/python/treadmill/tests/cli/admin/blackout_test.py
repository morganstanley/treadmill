"""Unit test for treadmill.cli.blackout.logs."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click.testing
import mock

from treadmill import context
from treadmill import plugin_manager
from treadmill import zkutils

from treadmill.scheduler import masterapi


class AdminBlackoutTest(unittest.TestCase):
    """Mock test for treadmill.cli.admin.blackout"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.blackout_mod = plugin_manager.load(
            'treadmill.cli.admin', 'blackout'
        )
        self.blackout_cli = self.blackout_mod.init()
        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'
        context.GLOBAL.zk = mock.Mock()

    def test_list_app_blackouts(self):
        """Test listing app blackouts."""
        context.GLOBAL.zk.conn.get.return_value = (
            """
                foo.*: {reason: test, when: 1234567890.0}
                bar.baz: {reason: test, when: 1234567890.0}
            """,
            mock.Mock()
        )

        res = self.runner.invoke(
            self.blackout_cli,
            ['--cell', 'test', 'app']
        )

        self.assertEqual(res.exit_code, 0)
        self.assertEqual(
            res.output,
            '[Fri, 13 Feb 2009 23:31:30+0000] bar.baz test\n'
            '[Fri, 13 Feb 2009 23:31:30+0000] foo.* test\n'
        )

        context.GLOBAL.zk.conn.get.return_value = (None, mock.Mock())

        res = self.runner.invoke(
            self.blackout_cli,
            ['--cell', 'test', 'app']
        )
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.output, '')

    @mock.patch('time.time', mock.Mock(return_value=1234567890.0))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_event', mock.Mock())
    def test_blackout_app(self):
        """Test app blackout."""
        context.GLOBAL.zk.conn.get.return_value = (
            """
                foo.*: {reason: test, when: 1234567890.0}
            """,
            mock.Mock()
        )

        res = self.runner.invoke(
            self.blackout_cli,
            ['--cell', 'test', 'app', '--app', 'bar.baz', '--reason', 'test']
        )

        self.assertEqual(res.exit_code, 0)
        self.assertEqual(
            res.output,
            '[Fri, 13 Feb 2009 23:31:30+0000] bar.baz test\n'
            '[Fri, 13 Feb 2009 23:31:30+0000] foo.* test\n'
        )

        zkutils.put.assert_called_once_with(
            mock.ANY,
            '/blackedout.apps',
            data={
                'foo.*': {'when': 1234567890.0, 'reason': 'test'},
                'bar.baz': {'when': 1234567890.0, 'reason': 'test'}
            }
        )
        masterapi.create_event.assert_called_once_with(
            mock.ANY, 0, 'apps_blacklist', None
        )

        zkutils.put.reset_mock()
        masterapi.create_event.reset_mock()

        context.GLOBAL.zk.conn.get.return_value = (None, mock.Mock())

        res = self.runner.invoke(
            self.blackout_cli,
            ['--cell', 'test', 'app', '--app', 'foo.*', '--reason', 'test']
        )

        self.assertEqual(res.exit_code, 0)
        self.assertEqual(
            res.output,
            '[Fri, 13 Feb 2009 23:31:30+0000] foo.* test\n'
        )

        zkutils.put.assert_called_once_with(
            mock.ANY,
            '/blackedout.apps',
            data={'foo.*': {'when': 1234567890.0, 'reason': 'test'}}
        )
        masterapi.create_event.assert_called_once_with(
            mock.ANY, 0, 'apps_blacklist', None
        )

    @mock.patch('time.time', mock.Mock(return_value=1234567890.0))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_event', mock.Mock())
    def test_clear_app_blackout(self):
        """Test clearing app blackout."""
        context.GLOBAL.zk.conn.get.return_value = (
            """
                foo.*: {reason: test, when: 1234567890.0}
                bar.baz: {reason: test, when: 1234567890.0}
            """,
            mock.Mock()
        )

        res = self.runner.invoke(
            self.blackout_cli,
            ['--cell', 'test', 'app', '--app', 'bar.baz', '--clear']
        )

        self.assertEqual(res.exit_code, 0)
        self.assertEqual(
            res.output,
            '[Fri, 13 Feb 2009 23:31:30+0000] foo.* test\n'
        )

        zkutils.put.assert_called_once_with(
            mock.ANY,
            '/blackedout.apps',
            data={'foo.*': {'when': 1234567890.0, 'reason': 'test'}}
        )
        masterapi.create_event.assert_called_once_with(
            mock.ANY, 0, 'apps_blacklist', None
        )


if __name__ == '__main__':
    unittest.main()
