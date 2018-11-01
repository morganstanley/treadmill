"""Unit test for treadmill.cli.admin.ldap.allocation."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

from treadmill import admin
from treadmill import plugin_manager


class AdminLdapAllocationTest(unittest.TestCase):
    """Mock test for treadmill.cli.admin.ldap.allocation"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.alloc_mod = plugin_manager.load(
            'treadmill.cli.admin.ldap', 'allocation'
        )
        self.alloc_cli = self.alloc_mod.init()

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={
                    'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                }))
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    def test_assign_update(self):
        """Test updating assignment, append assignment to existing assignments.
        """
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test/dev',
                '--cell', 'cell',
                '--pattern', 'foo.baz*',
                '--priority', '1',
            ]
        )

        self.assertEqual(res.exit_code, 0)
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
                mock.Mock(return_value={'cell': 'cell'}))
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    def test_assign_update_empty(self):
        """Test updating assignment, append assignment to empty cell alloc.
        """
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test/dev',
                '--cell', 'cell',
                '--pattern', 'foo.bar*',
                '--priority', '1',
            ]
        )

        self.assertEqual(res.exit_code, 0)
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
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    def test_assign_update_priority(self):
        """Test updating assignment, update priority of an existing assignment.
        """
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test/dev',
                '--cell', 'cell',
                '--pattern', 'foo.bar*',
                '--priority', '100',
            ]
        )

        self.assertEqual(res.exit_code, 0)
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
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    def test_assign_delete(self):
        """Test deleting assignment.
        """
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test/dev',
                '--cell', 'cell',
                '--pattern', 'foo.baz*',
                '--priority', '1',
                '--delete'
            ]
        )

        self.assertEqual(res.exit_code, 0)
        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                ]
            }
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.CellAllocation.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.CellAllocation.get',
                mock.Mock(return_value={
                    'assignments': [
                        {'pattern': 'foo.bar*', 'priority': 1},
                        {'pattern': 'foo.baz*', 'priority': 1},
                    ]
                }))
    def test_assign_delete_nonexistent(self):
        """Test deleting nonexistent assignment.
        """
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test/dev',
                '--cell', 'cell',
                '--pattern', 'foo.nonexistent*',
                '--priority', '1',
                '--delete'
            ]
        )

        self.assertEqual(res.exit_code, 0)
        # Assignment should be untouched
        admin.CellAllocation.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                    {'pattern': 'foo.baz*', 'priority': 1},
                ]
            },
        )


if __name__ == '__main__':
    unittest.main()
