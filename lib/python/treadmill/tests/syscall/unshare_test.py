"""Unit test for unshare python wrapper.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

from treadmill.syscall import unshare


class UnshareTest(unittest.TestCase):
    """Tests unshare module constants."""

    def test_constants(self):
        """Verifies the the wrapper contains needed constants."""
        self.assertTrue(getattr(unshare, 'CLONE_NEWNS'))
        self.assertTrue(getattr(unshare, 'CLONE_NEWNET'))


if __name__ == '__main__':
    unittest.main()
