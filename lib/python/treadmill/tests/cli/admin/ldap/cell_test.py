"""unit test for treadmill.cli.admin.ldap.cell."""
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


class AdminLdapCellTest(unittest.TestCase):
    """Mock test for treadmill.cli.admin.ldap.cell"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.cell_mod = plugin_manager.load(
            'treadmill.cli.admin.ldap', 'cell'
        )
        self.cell_cli = self.cell_mod.init()

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.create',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={
                    'version': '1.0.0',
                    'location': 'na.ny',
                    'username': 'treadmill',
                    'root': '/opt/treadmill',
                    '_id': 'mycell',
                }))
    @mock.patch('treadmill.admin.Allocation.get',
                mock.Mock(return_value={}))
    def test_cell_configure(self):
        """test cell create
        """
        res = self.runner.invoke(
            self.cell_cli,
            [
                'configure',
                '--version', '1.0.0',
                '--location', 'na.ny',
                '--username', 'treadmill',
                '--root', '/opt/treadmill',
                'mycell',
            ]
        )
        self.assertEqual(res.exit_code, 0)
        admin.Cell.create.assert_called_once_with(
            'mycell',
            {
                'version': '1.0.0',
                'location': 'na.ny',
                'username': 'treadmill',
                'root': '/opt/treadmill',
            }
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={
                    'version': '1.0.0',
                    'location': 'na.ny',
                    'username': 'treadmill',
                    'root': '/opt/treadmill',
                    '_id': 'mycell',
                }))
    def test_cell_insert_new(self):
        """test cell create
        """
        res = self.runner.invoke(
            self.cell_cli,
            [
                'insert',
                'mycell',
                '--idx', '1',
                '--hostname', 'foo',
                '--client-port', '4000',
                '--jmx-port', '4100',
                '--followers-port', '4200',
                '--election-port', '4300',
            ]
        )
        self.assertEqual(res.exit_code, 0)
        admin.Cell.update.assert_called_once_with(
            'mycell',
            {
                'masters': [{
                    'idx': 1,
                    'hostname': 'foo',
                    'zk-client-port': 4000,
                    'zk-jmx-port': 4100,
                    'zk-followers-port': 4200,
                    'zk-election-port': 4300,
                }]
            }
        )

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.update',
                mock.Mock(return_value=None))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={
                    'version': '1.0.0',
                    'location': 'na.ny',
                    'username': 'treadmill',
                    'root': '/opt/treadmill',
                    '_id': 'mycell',
                    'masters': [{'idx': '1'}],
                }))
    def test_cell_insert_existing(self):
        """test cell create
        """
        res = self.runner.invoke(
            self.cell_cli,
            [
                'insert',
                'mycell',
                '--idx', '1',
                '--hostname', 'foo',
                '--client-port', '4000',
                '--jmx-port', '4100',
                '--followers-port', '4200',
                '--election-port', '4300',
            ]
        )
        self.assertEqual(res.exit_code, 0)
        admin.Cell.update.assert_called_once_with(
            'mycell',
            {
                'masters': [{
                    'idx': 1,
                    'hostname': 'foo',
                    'zk-client-port': 4000,
                    'zk-jmx-port': 4100,
                    'zk-followers-port': 4200,
                    'zk-election-port': 4300,
                }]
            }
        )


if __name__ == '__main__':
    unittest.main()
