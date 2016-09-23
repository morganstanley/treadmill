"""Allocation REST api tests."""
import unittest

import tests.treadmill_test_deps  # pylint: disable=W0611
from treadmill.rest.v3 import allocation


class RestAllocationTest(unittest.TestCase):
    """treadmill.rest.v3.allocation tests."""

    # pylint: disable=W0212
    def test_alloc_id(self):
        """Checking _alloc_id() functionality."""
        self.assertEqual(allocation._alloc_id(), ['*-*'])
        self.assertEqual(allocation._alloc_id('tenant'), ['tenant-*'])
        self.assertEqual(allocation._alloc_id('tenant', 'allocation'),
                         ['tenant-allocation'])
        self.assertEqual(allocation._alloc_id('tenant', 'allocation', 'cell'),
                         ['tenant-allocation', 'cell'])


if __name__ == '__main__':
    unittest.main()
