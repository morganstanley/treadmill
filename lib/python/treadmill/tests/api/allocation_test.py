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
        self.alloc_api = allocation.API()

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
        self.alloc_api.list()
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
        """Dummy test for treadmill.api.allocation.create()"""
        alloc_admin = admin.CellAllocation(None)
        self.alloc_api.reservation.create(
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

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={
                    'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                }))
    def test_assignment_update(self):
        """Test updating assignment, append assignment to existing assignments.
        """
        res = self.alloc_api.assignment.update(
            'test/dev/cell/foo.baz*', {'priority': 1}
        )

        self.assertEqual(
            res,
            [
                {'pattern': 'foo.bar*', 'priority': 1},
                {'pattern': 'foo.baz*', 'priority': 1},
            ]
        )
        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                    {'pattern': 'foo.baz*', 'priority': 1},
                ]
            }
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={}))
    def test_assignment_update_empty(self):
        """Test updating assignment, append assignment to empty cell alloc.
        """
        res = self.alloc_api.assignment.update(
            'test/dev/cell/foo.bar*', {'priority': 1}
        )

        self.assertEqual(res, [{'pattern': 'foo.bar*', 'priority': 1}])
        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]}
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={
                    'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                }))
    def test_assignment_update_priority(self):
        """Test updating assignment, update priority of an existing assignment.
        """
        res = self.alloc_api.assignment.update(
            'test/dev/cell/foo.bar*', {'priority': 100}
        )

        self.assertEqual(res, [{'pattern': 'foo.bar*', 'priority': 100}])
        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {'assignments': [{'pattern': 'foo.bar*', 'priority': 100}]}
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={
                    'assignments': [
                        {'pattern': 'foo.bar*', 'priority': 1},
                        {'pattern': 'foo.baz*', 'priority': 1},
                    ]
                }))
    def test_assignment_delete(self):
        """Test deleting assignment.
        """
        self.alloc_api.assignment.delete('test/dev/cell/foo.baz*')

        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                ]
            }
        )

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={}))
    def test_assignment_delete_nonexistent(self):
        """Test deleting nonexistent assignment.
        """
        self.alloc_api.assignment.delete('test/dev/cell/foo.nonexistent*')

        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': []
            }
        )


if __name__ == '__main__':
    unittest.main()
