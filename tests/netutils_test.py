"""Unit test for netutils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import socket
import sys
import unittest

from treadmill import netutils


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
class NetutilsTest(unittest.TestCase):
    """Tests for teadmill.netutils
    """

    def test_netstat_listen_0_0_0_0(self):
        """Tests netutils.netstat"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        self.assertIn(port, netutils.netstat(os.getpid()))
        sock.close()

    def test_netstat_listen_127_0_0_1(self):
        """Tests netutils.netstat"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        # Do not report ports listening on 127.0.0.1
        self.assertNotIn(port, netutils.netstat(os.getpid()))
        sock.close()


if __name__ == '__main__':
    unittest.main()
