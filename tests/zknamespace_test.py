"""Unit test for zknamespace.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import zknamespace as z


class ZkNamespaceTest(unittest.TestCase):
    """Tests for teadmill.zknamespace."""

    def test_path(self):
        """Tests zknamespace functions.
        """
        self.assertEqual('/servers/aaa', z.path.server('aaa'))
        self.assertEqual('/scheduled/aaa', z.path.scheduled('aaa'))
        self.assertEqual('/trace/00D2', z.path.trace('ddd.rrr#1234567890'))


if __name__ == '__main__':
    unittest.main()
