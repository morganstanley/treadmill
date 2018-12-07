"""unit test for treadmill.cli.admin.ldap.cell."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

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

    @mock.patch('treadmill.context.AdminContext.cell')
    @mock.patch('treadmill.context.AdminContext.allocation',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {}
                })))
    def test_cell_configure(self, cell_factory):
        """test cell create
        """
        admin_cell = cell_factory.return_value
        admin_cell.create.return_value = None
        admin_cell.get.return_value = {
            'version': '1.0.0',
            'location': 'na.ny',
            'username': 'treadmill',
            'root': '/opt/treadmill',
            '_id': 'mycell',
        }

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
        admin_cell.create.assert_called_once_with(
            'mycell',
            {
                'version': '1.0.0',
                'location': 'na.ny',
                'username': 'treadmill',
                'root': '/opt/treadmill',
            }
        )

    @mock.patch('treadmill.context.AdminContext.cell')
    def test_cell_insert_new(self, cell_factory):
        """test cell create
        """
        admin_cell = cell_factory.return_value
        admin_cell.update.return_value = None
        admin_cell.get.return_value = {
            'version': '1.0.0',
            'location': 'na.ny',
            'username': 'treadmill',
            'root': '/opt/treadmill',
            '_id': 'mycell',
        }

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
        admin_cell.update.assert_called_once_with(
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

    @mock.patch('treadmill.context.AdminContext.cell')
    def test_cell_insert_existing(self, cell_factory):
        """test cell create
        """
        admin_cell = cell_factory.return_value
        admin_cell.update.return_value = None
        admin_cell.get.return_value = {
            'version': '1.0.0',
            'location': 'na.ny',
            'username': 'treadmill',
            'root': '/opt/treadmill',
            '_id': 'mycell',
            'masters': [{'idx': '1'}],
        }

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
        admin_cell.update.assert_called_once_with(
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
