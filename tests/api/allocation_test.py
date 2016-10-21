"""Allocation API tests."""
import unittest

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

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Allocation.list',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.admin.CellAllocation.list',
                mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.allocation._list()"""
        alloc_admin = admin.Allocation(None)
        self.alloc.list()
        alloc_admin.list.assert_called_with({})


if __name__ == '__main__':
    unittest.main()
