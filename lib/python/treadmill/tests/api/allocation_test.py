"""Allocation API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill.api import allocation


class ApiAllocationTest(unittest.TestCase):
    """treadmill.api.allocation tests."""

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def setUp(self):
        self.alloc = allocation.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock()))
    @mock.patch('treadmill.context.AdminContext.cellAllocation',
                mock.Mock(return_value=mock.Mock(**{'list.return_value': []})))
    def test_list(self):
        """Dummy test for treadmill.api.allocation._list()"""
        alloc_admin = treadmill.context.AdminContext.allocation.return_value
        alloc_admin.list.return_value = []
        self.alloc.list()
        alloc_admin.list.assert_called_with({})

    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': {},
                    'get.return_value': {'environment': 'prod'},
                })))
    @mock.patch('treadmill.context.AdminContext.cellAllocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': {},
                    'get.return_value': {},
                })))
    @mock.patch('treadmill.api.allocation._check_capacity',
                mock.Mock(return_value=True))
    def test_reservation(self):
        """Dummy test for treadmill.api.allocation.create()"""
        alloc_admin = treadmill.context.AdminContext.cellAllocation.return_value
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
