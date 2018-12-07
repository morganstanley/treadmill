"""Unit test for supervision management utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

from treadmill.supervisor import _utils as supervisor_utils


class UtilsTest(unittest.TestCase):
    """Mock test for treadmill.supervisor._utils.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_data_write(self):
        """Test writing string to a file with newline added.
        """
        filename = os.path.join(self.root, 'foo')

        supervisor_utils.data_write(filename, 'bar')

        with io.open(filename) as f:
            self.assertEqual(f.read(), 'bar\n')
        if os.name == 'posix':
            self.assertEqual(os.stat(filename).st_mode, 0o100644)

        # Test creating an empty file.
        filename = os.path.join(self.root, 'baz')

        supervisor_utils.data_write(filename, None)

        self.assertTrue(os.path.exists(filename))
        if os.name == 'posix':
            self.assertEqual(os.stat(filename).st_mode, 0o100644)

    def test_value_write(self):
        """Test writing an integer value to a file.
        """
        filename = os.path.join(self.root, 'foo')

        supervisor_utils.value_write(filename, 0)

        with io.open(filename) as f:
            self.assertEqual(f.read(), '0\n')
        if os.name == 'posix':
            self.assertEqual(os.stat(filename).st_mode, 0o100644)

    def test_environ_dir_write(self):
        """Test creating environment directory suitable for envdir.
        """
        env_dir = os.path.join(self.root, 'env_dir')
        os.mkdir(env_dir)

        supervisor_utils.environ_dir_write(
            env_dir, {'foo': 'bar', 'baz': '0', 'empty': None}
        )

        with io.open(os.path.join(env_dir, 'foo'), 'rb') as f:
            self.assertEqual(f.read(), b'bar')
        if os.name == 'posix':
            self.assertEqual(
                os.stat(os.path.join(env_dir, 'foo')).st_mode, 0o100644
            )
        with io.open(os.path.join(env_dir, 'baz'), 'rb') as f:
            self.assertEqual(f.read(), b'0')
        if os.name == 'posix':
            self.assertEqual(
                os.stat(os.path.join(env_dir, 'baz')).st_mode, 0o100644
            )
        self.assertTrue(os.path.exists(os.path.join(env_dir, 'empty')))
        if os.name == 'posix':
            self.assertEqual(
                os.stat(os.path.join(env_dir, 'empty')).st_mode, 0o100644
            )

    def test_script_write(self):
        """Test writing a script to a file.
        """
        filename = os.path.join(self.root, 'foo')

        supervisor_utils.script_write(filename, 'script')

        with io.open(filename) as f:
            if os.name == 'posix':
                self.assertEqual(f.read(), 'script\n\n')
                self.assertEqual(os.stat(filename).st_mode, 0o100755)
            else:
                self.assertEqual(f.read(), 'script')


if __name__ == '__main__':
    unittest.main()
