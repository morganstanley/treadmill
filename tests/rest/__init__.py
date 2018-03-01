"""Tests for treadmill.rest.*"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os.path
import tempfile
import unittest
from unittest import mock

from treadmill import rest


# W0212: Access to a protected member of a client class
# pylint: disable=W0212
class UdsRestServerTest(unittest.TestCase):
    """Test for treadmill.rest.UdsRestServer."""

    def test_udsrestsrv(self):
        """Dummy test."""
        socket = os.path.join(
            tempfile.gettempdir(), 'no', 'such', 'dir', 'foo.sock'
        )
        rest_server = rest.UdsRestServer(socket)

        # not yet existing socket w/ containing dir should be created
        rest_server._setup_endpoint(mock.Mock())
        self.assertTrue(os.path.exists(socket))

        # shouldn't fail if the containing dir already exists
        rest_server._setup_endpoint(mock.Mock())


if __name__ == '__main__':
    unittest.main()
