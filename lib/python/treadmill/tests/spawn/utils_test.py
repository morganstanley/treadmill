"""Unit test for treadmill.spawn.utils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import spawn
from treadmill.spawn import utils


class UtilsTest(unittest.TestCase):
    """Tests for teadmill.spawn.utils."""

    def test_get_instance_path(self):
        """Tests that getting the instance path works correctly."""
        paths = spawn.SpawnPaths('/does/not/exist', 1)
        job, bucket, running = utils.get_instance_path('test.yml', paths)
        self.assertEqual(job, '/does/not/exist/apps/jobs/test')
        self.assertEqual(bucket, '/does/not/exist/running/000000')
        self.assertEqual(running, '/does/not/exist/running/000000/test')

        job, bucket, running = utils.get_instance_path('test', paths)
        self.assertEqual(job, '/does/not/exist/apps/jobs/test')
        self.assertEqual(bucket, '/does/not/exist/running/000000')
        self.assertEqual(running, '/does/not/exist/running/000000/test')

    def test_get_instance_path_with_dot(self):
        """Tests that getting the instance path works correctly with a '.'."""
        paths = spawn.SpawnPaths('/does/not/exist', 1)
        job, bucket, running = utils.get_instance_path('test.dot.yml', paths)
        self.assertEqual(job, '/does/not/exist/apps/jobs/test.dot')
        self.assertEqual(bucket, '/does/not/exist/running/000000')
        self.assertEqual(running, '/does/not/exist/running/000000/test.dot')

        job, bucket, running = utils.get_instance_path('test.dot', paths)
        self.assertEqual(job, '/does/not/exist/apps/jobs/test.dot')
        self.assertEqual(bucket, '/does/not/exist/running/000000')
        self.assertEqual(running, '/does/not/exist/running/000000/test.dot')


if __name__ == '__main__':
    unittest.main()
