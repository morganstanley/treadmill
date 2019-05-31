"""Unit test for netutils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import sys
import unittest

import mock
import pkg_resources

from treadmill import netutils


def _test_data(name):
    data_path = os.path.join('data', name)
    with pkg_resources.resource_stream(__name__, data_path) as f:
        return f.read().decode()


def _net_tcp_open(f, *args, **kwargs):
    """Mock tcp/tcp6 open."""
    if f.endswith('/tcp'):
        data = _test_data('proc.net.tcp.data')
        return mock.mock_open(read_data=data)(f, *args, **kwargs)
    if f.endswith('/tcp6'):
        data = _test_data('proc.net.tcp6.data')
        return mock.mock_open(read_data=data)(f, *args, **kwargs)
    else:
        return io.open.return_value


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
class NetutilsTest(unittest.TestCase):
    """Tests for teadmill.netutils

    The test uses two mock outputs from /proc/net/tcp and /proc/net/tcp6.

    On tcp6, it listens on port 1 on ::, and port 2 on ::1 - loopback.
    On tcp, list on 0.0.0.0:3 and 127.0.0.1:4.

    Loopback ports are ignored. Other lines - where state is not listen, are
    ignored.

    """

    @mock.patch('io.open', mock.mock_open())
    def test_netstat(self):
        """Tests netutils.netstat"""
        io.open.side_effect = _net_tcp_open
        self.assertIn(1, netutils.netstat(os.getpid()))
        self.assertNotIn(2, netutils.netstat(os.getpid()))
        self.assertIn(3, netutils.netstat(os.getpid()))
        self.assertNotIn(4, netutils.netstat(os.getpid()))


if __name__ == '__main__':
    unittest.main()
