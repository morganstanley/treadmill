"""
Unit test for treadmill.cli.aws
"""

import importlib
import unittest
import click
import click.testing
import mock
import os
import treadmill


class AwsTest(unittest.TestCase):
    """Test for treadmill.cli.aws"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.aws').init()

    @mock.patch('treadmill.cli.aws.PlaybookCLI')
    def test_cell_without_create(self, playbook_cli_mock):
        """Test cli.aws.cell without create option"""

        self.runner.invoke(
            self.configure_cli,
            ['cell']
        )
        self.assertFalse(playbook_cli_mock.called)

    @mock.patch('treadmill.cli.aws.PlaybookCLI')
    def test_cell_with_create(self, playbook_cli_mock):
        """Test cli.aws.cell with create option"""

        playbook_cli_obj_mock = mock.Mock(
            **{
                'parse.return_value': None,
                'run.return_value': None
            }
        )
        playbook_cli_mock.return_value = playbook_cli_obj_mock

        self.runner.invoke(self.configure_cli, ['cell', '--create'])

        playbook_cli_mock.assert_called_once_with([
            'ansible-playbook',
            '-i',
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'controller.inventory',
            ),
            '-e',
            'aws_config=' + os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'config/aws.yml'
            ),
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'cell.yml',
            ),
            '--key-file',
            'key.pem',
        ])

        playbook_cli_obj_mock.parse.assert_called_once()
        playbook_cli_obj_mock.run.assert_called_once()

    @mock.patch('treadmill.cli.aws.PlaybookCLI')
    def test_cell_with_destroy(self, playbook_cli_mock):
        """Test cli.aws.cell with destroy option"""

        playbook_cli_obj_mock = mock.Mock(
            **{
                'parse.return_value': None,
                'run.return_value': None
            }
        )
        playbook_cli_mock.return_value = playbook_cli_obj_mock

        self.runner.invoke(self.configure_cli, ['cell', '--destroy'])

        playbook_cli_mock.assert_called_once_with([
            'ansible-playbook',
            '-i',
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'controller.inventory',
            ),
            '-e',
            'aws_config=' + os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'config/aws.yml'
            ),
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'destroy-cell.yml',
            ),
        ])

        playbook_cli_obj_mock.parse.assert_called_once()
        playbook_cli_obj_mock.run.assert_called_once()

    @mock.patch('treadmill.cli.aws.PlaybookCLI')
    def test_node_without_create(self, playbook_cli_mock):
        """Test cli.aws.node without create option"""
        self.runner.invoke(
            self.configure_cli,
            ['node']
        )
        self.assertFalse(playbook_cli_mock.called)

    @mock.patch('treadmill.cli.aws.PlaybookCLI')
    def test_node_with_create(self, playbook_cli_mock):
        """Test cli.aws.node with create option"""

        playbook_cli_obj_mock = mock.Mock(
            **{
                'parse.return_value': None,
                'run.return_value': None
            }
        )
        playbook_cli_mock.return_value = playbook_cli_obj_mock

        self.runner.invoke(self.configure_cli, ['node', '--create'])

        playbook_cli_mock.assert_called_once_with([
            'ansible-playbook',
            '-i',
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'controller.inventory',
            ),
            os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'node.yml',
            ),
            '--key-file',
            'key.pem',
            '-e',
            'aws_config=' + os.path.join(
                treadmill.TREADMILL_DEPLOY_PACKAGE,
                'config/aws.yml'
            )
        ])

        playbook_cli_obj_mock.parse.assert_called_once()
        playbook_cli_obj_mock.run.assert_called_once()

    @mock.patch('treadmill.cli.aws.copy_tree')
    def test_aws_init(self, copy_tree_mock):
        """Test treadmill CLI init"""

        self.runner.invoke(
            self.configure_cli,
            ['init']
        )
        copy_tree_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
