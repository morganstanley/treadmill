"""Unit test for treadmill.cli.ssh
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
from gevent import queue as g_queue
import mock

from treadmill import plugin_manager


class BadExit(Exception):
    """Test exception.
    """


class SshTest(unittest.TestCase):
    """Mock test for treadmill.cli.ssh"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.ssh_mod = plugin_manager.load('treadmill.cli', 'ssh')
        self.ssh_cli = self.ssh_mod.init()

    @unittest.skip('Broken test cause by inter-deps')  # XXX: Fixme
    @mock.patch('treadmill.cli.ssh.run_ssh', mock.Mock())
    @mock.patch('treadmill.cli.ssh._connect')
    def test_wait_for_ssh(self, mock_conn):
        """Test the _wait_for_ssh() helper func."""

        # if the connection attempts fail
        mock_conn.return_value = False
        queue = g_queue.JoinableQueue(
            items=[('dummy.host', 1234), ('host', 1234)]
        )

        # W0212: don't compain about protected member access
        # pylint: disable=W0212
        self.ssh_mod._wait_for_ssh(queue, 'ssh', 'cmd', timeout=0, attempts=10)
        self.assertEqual(mock_conn.call_count, 10)
        # check that "task_done()" has been invoked as many times as elements
        # have been read from the queue
        with self.assertRaises(ValueError):
            queue.task_done()

        # if the connection attempt is successful
        mock_conn.reset_mock()
        mock_conn.return_value = True
        queue = g_queue.JoinableQueue(
            items=[('dummy.host', 1234), ('host', 1234)]
        )
        self.ssh_mod._wait_for_ssh(queue, 'ssh', 'cmd', timeout=0, attempts=5)
        self.assertEqual(mock_conn.call_count, 1)

        # first two attempts fail, then new endpoint info is taken from the
        # queue and the new attempt is successful
        mock_conn.reset_mock()
        # connection attempt successful only at the third (host_B) attempt
        mock_conn.side_effect = lambda host, port: host == 'host_B'
        queue = g_queue.JoinableQueue(items=[('dummy.host', 1234),
                                             ('host_A', 1234),
                                             ('host_B', 1234)])

        self.ssh_mod._wait_for_ssh(queue, 'ssh', 'cmd', timeout=0, attempts=5)
        self.assertEqual(mock_conn.call_count, 3)

        with self.assertRaises(ValueError):
            queue.task_done()

    @mock.patch('treadmill.cli.bad_exit', side_effect=BadExit())
    def test_run_unix(self, bad_exit):
        """Test run_unix()."""
        with self.assertRaises(BadExit):
            self.ssh_mod.run_unix('host', 'port', 'no_such_ssh_cmd', 'cmd')
            self.assertTrue(bad_exit.called())

    @mock.patch('treadmill.cli.bad_exit', side_effect=BadExit())
    def test_run_putty(self, bad_exit):
        """Test run_putty()."""
        with self.assertRaises(BadExit):
            self.ssh_mod.run_putty('host', 'port', 'no_such_putty_cmd', 'cmd')
            self.assertTrue(bad_exit.called())


if __name__ == '__main__':
    unittest.main()
