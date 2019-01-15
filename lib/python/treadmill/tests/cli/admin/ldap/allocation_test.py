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
from treadmill.admin import exc as admin_exceptions


class AdminLdapAllocationTest(unittest.TestCase):
    """Mock test for treadmill.cli.admin.ldap.allocation"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.alloc_mod = plugin_manager.load(
            'treadmill.cli.admin.ldap', 'allocation'
        )
        self.alloc_cli = self.alloc_mod.init()

    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.side_effect': admin_exceptions.NoSuchObjectResult,
                    'create.return_value': None
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_tenant_create(self):
        """Test creating a tenant.
        """
        tenant_admin = treadmill.context.AdminContext.tenant.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'configure',
                'test',
                '-s', '123',
            ]
        )

        self.assertEqual(res.exit_code, 0)
        tenant_admin.get.assert_called_once_with('test')
        tenant_admin.create.assert_called_once_with(
            'test',
            {'systems': ['123']}
        )

    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                    'update.return_value': None
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_tenant_update(self):
        """Test update a tenant twice. One with appending systems,
        Second with setting systems.
        """
        tenant_admin = treadmill.context.AdminContext.tenant.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'configure',
                'test',
                '--add-systems', '456'
            ]
        )

        self.assertEqual(res.exit_code, 0)

        res = self.runner.invoke(
            self.alloc_cli,
            [
                'configure',
                'test',
                '-s', '456',
            ]
        )

        self.assertEqual(res.exit_code, 0)

        get_calls = [mock.call('test')] * 2
        tenant_admin.get.assert_has_calls(
            get_calls,
            any_order=False
        )

        update_calls = [
            mock.call('test', {'systems': ['123', '456']}),
            mock.call('test', {'systems': ['456']})
        ]
        tenant_admin.update.assert_has_calls(
            update_calls,
            any_order=False
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': None,
                    'get.side_effect': admin_exceptions.NoSuchObjectResult,
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.return_value': None
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_reservation_create(self):
        """Test creating a reservation.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'reserve',
                'test',
                '--cell', 'cell',
                '--env', 'dev',
            ]
        )

        self.assertEqual(res.exit_code, 0)
        ca_admin.get.assert_called_once_with(['cell', 'test/dev'])
        ca_admin.create.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'disk': '0M',
                'cpu': '0%',
                'memory': '0M',
                'partition': '_default',
                'rank': 100
            }
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value':
                    {
                        'disk': '0M',
                        'cpu': '0%',
                        'memory': '0M',
                        'partition': '_default',
                        'rank': 100
                    },
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_reservation_update(self):
        """Test updating a reservation.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'reserve',
                'test',
                '--cell', 'cell',
                '--env', 'dev',
                '--rank', 99,
                '--partition', 'fake',
                '-c', '58%',
                '--memory', '66M'
            ]
        )

        self.assertEqual(res.exit_code, 0)
        ca_admin.get.assert_called_once_with(['cell', 'test/dev'])
        ca_admin.update.assert_called_once_with(
            ['cell', 'test/dev'],
            {
                'cpu': '58%',
                'memory': '66M',
                'partition': 'fake',
                'rank': 99
            }
        )

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'delete.return_value': None,
                    'get.return_value': {
                        'disk': '0M',
                        'cpu': '0%',
                        'memory': '0M',
                        'partition': '_default',
                        'rank': 100
                    },
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    def test_reservation_delete(self):
        """Test deleting a reservation.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'reserve',
                'test',
                '--cell', 'cell',
                '--env', 'dev',
                '--delete'
            ]
        )

        self.assertEqual(res.exit_code, 0)
        ca_admin.get.assert_not_called()
        ca_admin.delete.assert_called_once_with(['cell', 'test/dev'])

    @mock.patch('treadmill.context.AdminContext.cell_allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'update.return_value': None,
                    'get.return_value': {
                        'assignments': [{'pattern': 'foo.bar*', 'priority': 1}]
                    },
                })))
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_assign_update(self):
        """Test updating assignment, append assignment to existing assignments.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test',
                '--env', 'dev',
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
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_assign_update_empty(self):
        """Test updating assignment, append assignment to empty cell alloc.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value
        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test',
                '--env', 'dev',
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
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_assign_update_priority(self):
        """Test updating assignment, update priority of an existing assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test',
                '--env', 'dev',
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
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_assign_delete(self):
        """Test deleting assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test',
                '--env', 'dev',
                '--cell', 'cell',
                '--pattern', 'foo.baz*',
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
                    'create.side_effect': admin_exceptions.AlreadyExistsResult
                })))
    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'systems': [123], 'tenant': 'test'},
                })))
    @mock.patch('treadmill.cli.admin.ldap.allocation._display_tenant',
                mock.Mock(return_value=None))
    def test_assign_delete_nonexistent(self):
        """Test deleting nonexistent assignment.
        """
        ca_admin = treadmill.context.AdminContext.cell_allocation.return_value

        res = self.runner.invoke(
            self.alloc_cli,
            [
                'assign',
                'test',
                '--env', 'dev',
                '--cell', 'cell',
                '--pattern', 'foo.nonexistent*',
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
