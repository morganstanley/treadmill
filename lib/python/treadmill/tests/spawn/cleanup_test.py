"""Unit test for treadmill.spawn.cleanup.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill.spawn import cleanup


class CleanupTest(unittest.TestCase):
    """Tests for teadmill.spawn.cleanup."""

    # Disable W0212: Access to a protected member
    # pylint: disable=W0212

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('shutil.rmtree', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.spawn.cleanup.Cleanup._nuke', mock.Mock())
    def test_on_created(self):
        """Tests basic cleanup functionality."""
        watch = cleanup.Cleanup('/does/not/exist', 2)

        watch._on_created('test.yml')

        self.assertEqual(2, treadmill.fs.rm_safe.call_count)
        self.assertEqual(1, shutil.rmtree.call_count)
        self.assertEqual(1, treadmill.spawn.cleanup.Cleanup._nuke.call_count)

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('os.listdir', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.spawn.cleanup.Cleanup._on_created', mock.Mock())
    def test_sync(self):
        """Tests the initial sync of the manifests."""
        os.listdir.side_effect = [
            ['job1'],
        ]

        watch = cleanup.Cleanup('/does/not/exist', 2)
        watch.sync()

        treadmill.spawn.cleanup.Cleanup._on_created \
                 .assert_called_with('/does/not/exist/cleanup/job1')


if __name__ == '__main__':
    unittest.main()
