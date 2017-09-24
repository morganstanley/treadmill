"""Allocation API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Allocation.create',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={'environment': 'prod'}))
    @mock.patch('treadmill.admin.CellAllocation.create',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.api.allocation._check_capacity',
                mock.Mock(return_value=True))
    def test_reservation(self):
        """Dummy test for treadmill.api.allocation._list()"""
        alloc_admin = admin.CellAllocation(None)
        self.alloc.reservation.create(
            'tenant/alloc/cellname',
            {'memory': '1G',
             'cpu': '100%',
             'disk': '2G',
             'partition': None})
        alloc_admin.create.assert_called_with(
            ['cellname', 'tenant/alloc'],
            {'disk': '2G',
             'partition': None,
             'cpu': '100%',
             'rank': 100,
             'memory': '1G'},
        )


if __name__ == '__main__':
    unittest.main()
