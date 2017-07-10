"""Unit test for treadmill.cli.ssh
"""

import importlib
import unittest

import click
import click.testing
from gevent import queue as g_queue
import mock


# W0212: don't compain about protected member access
# C0103: don't complain about invalid variable name 'q'
# pylint: disable=W0212,C0103
class SshTest(unittest.TestCase):
    """Mock test for treadmill.cli.ssh"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.ssh_mod = importlib.import_module('treadmill.cli.ssh')
        self.ssh_cli = self.ssh_mod.init()

    @mock.patch('treadmill.cli.ssh.run_ssh', mock.Mock())
    @mock.patch('treadmill.checkout.connect')
    def test_wait_for_ssh(self, mock_conn):
        """Test the _wait_for_ssh() helper func."""

        # if the connection attempts fail
        mock_conn.return_value = False
        q = g_queue.JoinableQueue(items=[('dummy.host', 1234), ('host', 1234)])
        self.ssh_mod._wait_for_ssh(q, 'ssh', 'cmd', timeout=0, attempts=10)
        self.assertEqual(mock_conn.call_count, 10)
        # check that "task_done()" has been invoked as many times as elements
        # have been read from the queue
        with self.assertRaises(ValueError):
            q.task_done()

        # if the connection attempt is successful
        mock_conn.reset_mock()
        mock_conn.return_value = True
        q = g_queue.JoinableQueue(items=[('dummy.host', 1234), ('host', 1234)])
        self.ssh_mod._wait_for_ssh(q, 'ssh', 'cmd', timeout=0, attempts=5)
        self.assertEqual(mock_conn.call_count, 1)

        # first two attempts fail, then new endpoint info is taken from the
        # queue and the new attempt is successful
        mock_conn.reset_mock()
        # connection attempt successful only at the third (host_B) attempt
        mock_conn.side_effect = lambda host, port: host == 'host_B'
        q = g_queue.JoinableQueue(items=[('dummy.host', 1234),
                                         ('host_A', 1234),
                                         ('host_B', 1234)])

        self.ssh_mod._wait_for_ssh(q, 'ssh', 'cmd', timeout=0, attempts=5)
        self.assertEqual(mock_conn.call_count, 3)

        with self.assertRaises(ValueError):
            q.task_done()


if __name__ == '__main__':
    unittest.main()
