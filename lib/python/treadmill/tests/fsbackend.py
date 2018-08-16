"""Unit test for Treadmill rrdutils module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.scheduler import fsbackend


class FsBackendTest(unittest.TestCase):
    """FsBackend unit tests.
    """

    # pylint: disable=protected-access
    def test_fpath(self):
        """Test _fpath.
        """
        self.assertEqual(
            fsbackend._fpath('/root', 'a/b/c'),
            '/root/_a/_b/c'
        )

    def test_dpath(self):
        """Test _dpath.
        """
        self.assertEqual(
            fsbackend._dpath('/root', 'a/b/c'),
            '/root/_a/_b/_c'
        )


if __name__ == '__main__':
    unittest.main()
