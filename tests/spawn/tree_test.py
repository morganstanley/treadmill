"""Unit test for treadmill.spawn.tree.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows  # pylint: disable=W0611

import mock

from treadmill import fs
from treadmill import supervisor
from treadmill import utils
from treadmill.spawn import tree as spawn_tree


class TreeTest(unittest.TestCase):
    """Tests for teadmill.spawn.tree."""

    @mock.patch('os.listdir', mock.Mock())
    @mock.patch('shutil.rmtree', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.utils.create_script', mock.Mock())
    @mock.patch('treadmill.supervisor.create_environ_dir', mock.Mock())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    def test_create(self):
        """Tests creating tree."""
        os.listdir.side_effect = [
            ['testing'], ['testing'],
        ]

        tree = spawn_tree.Tree('/does/not/exist', 2, 5)
        tree.create()

        self.assertEqual(1, supervisor.create_environ_dir.call_count)
        self.assertEqual(8, fs.mkdir_safe.call_count)
        self.assertEqual(6, utils.create_script.call_count)
        self.assertEqual(2, shutil.rmtree.call_count)


if __name__ == '__main__':
    unittest.main()
