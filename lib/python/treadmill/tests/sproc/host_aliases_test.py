"""Unit tests for treadmill.sproc.alert_monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import tempfile
import unittest
import shutil
import socket

import mock

from treadmill.sproc import host_aliases as ha


# pylint: disable=protected-access
class HostAliasesTest(unittest.TestCase):
    """Test treadmill.sproc.host_aliases.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_generate_empty(self):
        """Test DNS retry."""

        dest = os.path.join(self.root, 'hosts')
        aliases = {}
        retry = {}
        original = '127.0.0.1       localhost localhost.localhost\n'
        ha._generate(aliases, original, dest, retry)

        with io.open(dest, 'r') as f:
            self.assertEqual(f.read(), original)

        self.assertFalse(retry)

    @mock.patch('socket.gethostbyname', mock.Mock(spec_set=True))
    def test_generate(self):
        """Test DNS retry."""

        dest = os.path.join(self.root, 'hosts')
        aliases = {'foo': 'some.host.com'}
        retry = set()
        original = '127.0.0.1       localhost localhost.localhost\n'
        socket.gethostbyname.return_value = '1.2.3.4'
        ha._generate(aliases, original, dest, retry)

        with io.open(dest, 'r') as f:
            self.assertEqual(
                f.read(), original + '1.2.3.4 some.host.com foo\n'
            )

        self.assertFalse(retry)

    @mock.patch('socket.gethostbyname', mock.Mock(spec_set=True))
    def test_generate_dnserror(self):
        """Test DNS retry."""

        dest = os.path.join(self.root, 'hosts')
        aliases = {'foo': 'some.host.com'}
        retry = set()
        original = '127.0.0.1       localhost localhost.localhost\n'
        socket.gethostbyname.side_effect = socket.gaierror
        ha._generate(aliases, original, dest, retry)

        with io.open(dest, 'r') as f:
            self.assertEqual(f.read(), original)

        self.assertTrue(retry)
