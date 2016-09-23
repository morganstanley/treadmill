"""Allocation API tests."""
import unittest
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill import admin
from treadmill.api import allocation


class ApiAllocationTest(unittest.TestCase):
    """treadmill.api.allocation tests."""

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def setUp(self):
        self.alloc = allocation.API()

    def tearDown(self):
        pass

    # pylint: disable=W0212
    def test_unpack(self):
        """Checking _unpack() functionality."""
        self.assertEqual(
            allocation._unpack(['tenant-allocation']),
            ('tenant-allocation', None))
        self.assertEqual(
            allocation._unpack(['tenant-allocation', 'cell']),
            ('tenant-allocation', 'cell'))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Allocation.list', mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.allocation._list()"""
        alloc_admin = admin.Allocation(None)
        self.alloc.list(['*-*'])
        alloc_admin.list.assert_called_with({'_id': '*-*'})
        self.alloc.list(['tenant-*'])
        alloc_admin.list.assert_called_with({'_id': 'tenant*-*'})
        self.alloc.list(['tenant-allocation'])
        alloc_admin.list.assert_called_with({'_id': 'tenant*-allocation'})


if __name__ == '__main__':
    unittest.main()
