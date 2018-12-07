"""Allocation API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill import exc
from treadmill.api import allocation


class ApiAllocationTest(unittest.TestCase):
    """treadmill.api.allocation tests."""

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=None))
    def setUp(self):
        self.alloc_api = allocation.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{'list.return_value': []})))
    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{'list.return_value': []})))
    def test_list(self):
        """Dummy test for treadmill.api.allocation._list()"""
        alloc_admin = treadmill.context.AdminContext.allocation.return_value
        self.alloc_api.list()
        alloc_admin.list.assert_called_with({})

    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': {},
                    'get.return_value': {'environment': 'prod'},
                })))
    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': {},
                    'get.return_value': {},
                })))
    @mock.patch('treadmill.api.allocation._check_capacity',
                mock.Mock(return_value=True))
    def test_reservation(self):
        """Dummy test for treadmill.api.allocation.create()"""
        alloc_adm = treadmill.context.AdminContext.cell_allocation.return_value
        self.alloc_api.reservation.create(
            'tenant/alloc/cellname',
            {'memory': '1G',
             'cpu': '100%',
             'disk': '2G',
             'partition': None})
        alloc_adm.create.assert_called_with(
            ['cellname', 'tenant/alloc'],
            {'disk': '2G',
             'partition': None,
             'cpu': '100%',
             'rank': 100,
             'memory': '1G'},
        )

    @mock.patch('treadmill.context.AdminContext.partition',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {
                        'cpu': '200%',
                        'memory': '100G',
                        'disk': '100G',
                        'limits': [
                            {
                                'trait': 'a',
                                'cpu': '100%',
                                'memory': '100G',
                                'disk': '100G',
                            }
                        ],
                    }
                })))
    @mock.patch('treadmill.context.AdminContext.cell_allocation')
    def test_capacity_checking(self, cell_alloc_factory):
        """Test capacity checking"""
        alloc_admin = cell_alloc_factory.return_value
        alloc_admin.get.return_value = {}
        alloc_admin.create.return_value = {}
        alloc_admin.list.return_value = [
            {
                '_id': 'tenant/alloc/cellname',
                'traits': ['a'],
                'cpu': '100%',
                'disk': '100G',
                'memory': '100G',
            }
        ]

        self.alloc_api.reservation.create(
            'tenant/alloc/cellname',
            {
                'cpu': '100%',
                'memory': '10G',
                'disk': '10G',
                'partition': 'ppp',
                'traits': ['a', 'b']
            }
        )
        alloc_admin.create.assert_called_with(
            ['cellname', 'tenant/alloc'],
            {'disk': '10G',
             'partition': 'ppp',
             'cpu': '100%',
             'rank': 100,
             'traits': ['a', 'b'],
             'memory': '10G'},
        )

        # let's add a reservation so we don't have anough free
        # capacity anymore
        alloc_admin.list.return_value = [
            {
                '_id': 'tenant/otheralloc/cellname',
                'traits': ['a'],
                'cpu': '100%',
                'disk': '95G',
                'memory': '10G',
            }
        ]
        with self.assertRaises(exc.InvalidInputError):
            self.alloc_api.reservation.create(
                'tenant/alloc/cellname',
                {
                    'cpu': '100%',
                    'memory': '10G',
                    'disk': '10G',
                    'partition': 'ppp',
                    'traits': ['a', 'b']
                }
            )

    @mock.patch('treadmill.api.allocation._check_capacity',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.context.AdminContext.cell_allocation')
    def test_reservation_update(self, ca_factory):
        """Test updating reservation.
        """
        alloc_admin = ca_factory.return_value
        alloc_admin.update.return_value = None
        alloc_admin.get.return_value = {
            '_id': 'test/dev/cell',
            'cpu': '100%',
            'memory': '100M',
            'disk': '1G',
            'rank': 100,
            'traits': [],
            'partition': 'partition',
            'cell': 'cell',
            'assignments': [
                {'pattern': 'foo.bar*', 'priority': 1},
                {'pattern': 'foo.baz*', 'priority': 1},
            ],
        }

        res = self.alloc_api.reservation.update(
            'test/dev/cell',
            {
                'cpu': '200%',
                'memory': '200M',
                'disk': '2G',
                'partition': 'partition',
            }
        )

        cell_alloc = {
            '_id': 'test/dev/cell',
            'cpu': '200%',
            'memory': '200M',
            'disk': '2G',
            'rank': 100,
            'traits': [],
            'partition': 'partition',
            'cell': 'cell',
            'assignments': [
                {'pattern': 'foo.bar*', 'priority': 1},
                {'pattern': 'foo.baz*', 'priority': 1},
            ],
        }
        self.assertEqual(res, cell_alloc)
        alloc_admin.update.assert_called_once_with(
            ['cell', 'test/dev'], cell_alloc
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {
                        'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                    },
                })))
    def test_assignment_update(self):
        """Test updating assignment, append assignment to existing assignments.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                    {'pattern': 'foo.baz*', 'priority': 1},
                ]
            }
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {},
                })))
    def test_assignment_update_empty(self):
        """Test updating assignment, append assignment to empty cell alloc.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.alloc_api.assignment.update(
            'test/dev/cell/foo.bar*', {'priority': 1}
        )

        self.assertEqual(res, [{'pattern': 'foo.bar*', 'priority': 1}])
        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]}
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {
                        'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                    },
                })))
    def test_assignment_update_priority(self):
        """Test updating assignment, update priority of an existing assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.alloc_api.assignment.update(
            'test/dev/cell/foo.bar*', {'priority': 100}
        )

        self.assertEqual(res, [{'pattern': 'foo.bar*', 'priority': 100}])
        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {'assignments': [{'pattern': 'foo.bar*', 'priority': 100}]}
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {
                        'assignments': [
                            {'pattern': 'foo.bar*', 'priority': 1},
                            {'pattern': 'foo.baz*', 'priority': 1},
                        ]
                    },
                })))
    def test_assignment_delete(self):
        """Test deleting assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        self.alloc_api.assignment.delete('test/dev/cell/foo.baz*')

        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                ]
            }
        )

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {},
                })))
    def test_assignment_delete_nonexistent(self):
        """Test deleting nonexistent assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        self.alloc_api.assignment.delete('test/dev/cell/foo.nonexistent*')

        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': []
            }
        )


if __name__ == '__main__':
    unittest.main()
