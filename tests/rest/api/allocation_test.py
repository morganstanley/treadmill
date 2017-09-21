"""Allocation REST api tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import unittest

import tests.treadmill_test_deps  # pylint: disable=W0611
from treadmill.rest.api import allocation


class RestAllocationTest(unittest.TestCase):
    """treadmill.rest.api.allocation tests."""

    # pylint: disable=W0212
    def test_alloc_id(self):
        """Checking _alloc_id() functionality."""
        self.assertEqual(allocation._alloc_id('tenant', 'allocation'),
                         'tenant/allocation')
        self.assertEqual(allocation._alloc_id('tenant', 'allocation', 'cell'),
                         'tenant/allocation/cell')


if __name__ == '__main__':
    unittest.main()
