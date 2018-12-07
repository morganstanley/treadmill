"""Unit test for treadmill.cli.admin.ldap.allocation."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

import treadmill
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

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {
                        'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                    },
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {},
                })))
    def test_assign_update(self):
        """Test updating assignment, append assignment to existing assignments.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
                    'get.return_value': {'cell': 'cell'},
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {},
                })))
    def test_assign_update_empty(self):
        """Test updating assignment, append assignment to empty cell alloc.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {},
                })))
    def test_assign_update_priority(self):
        """Test updating assignment, update priority of an existing assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {},
                })))
    def test_assign_delete(self):
        """Test deleting assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'assignments': [
                    {'pattern': 'foo.bar*', 'priority': 1},
                ]
            }
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
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {},
                })))
    def test_assign_delete_nonexistent(self):
        """Test deleting nonexistent assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

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
        ca_admin.update.assert_called_once_with(
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
