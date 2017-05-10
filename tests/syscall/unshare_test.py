"""Unit test for unshare python wrapper
"""

import unittest

from treadmill.syscall import unshare


class UnshareTest(unittest.TestCase):
    """Tests unshare module constants."""

    def test_constants(self):
        """Verifies the the wrapper contains needed constants."""
        self.assertTrue(getattr(unshare, 'CLONE_NEWNS'))
        self.assertTrue(getattr(unshare, 'CLONE_NEWNET'))


if __name__ == '__main__':
    unittest.main()
