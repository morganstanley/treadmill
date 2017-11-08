# flake8: noqa

import importlib
import unittest
import io

import click
import click.testing
import mock

from treadmill.cli.admin import install


def _open_side_effect_for_configs(path, *args):
    if path.endswith('/etc/linux.aliases'):
        return io.StringIO("cmd: /usr/bin/cmd")
    elif path.endswith('/local/linux/node.config.yml'):
        return io.StringIO("treadmill_cpu: 10%")
    elif path.endswith('/local/linux/master.config.yml'):
        return io.StringIO("broken_nodes_percent: 1%")
    elif path == 'custom1.config':
        return io.StringIO("cmd: /custom/cmd")
    elif path == 'custom2.config':
        return io.StringIO("treadmill_cpu: 90%")
    else:
        return open(path, *args)

# original = install._load_configs


# def wrap_func(config, default_file, ctx):
#     ctx.obj = {}
#     original(config, default_file, ctx)


@unittest.skip('BROKEN: click options parsing')
class AdminInstallTest(unittest.TestCase):
    """
    tests for treadmill.cli.admin.install
    """

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.install_cli = importlib.import_module(
            'treadmill.cli.admin.install').init()

    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_configs))
    @mock.patch('treadmill.cli.admin.install.bootstrap.MasterBootstrap')
    def test_install_master_with_default_config(self, mocked_bootstrap):
        with mock.patch.object(install,
                               '_load_configs',
                               wraps=wrap_func):
            self.runner.invoke(
                self.install_cli,
                ['--cell', '-',
                 '--zookeeper', 'zk',
                 'master',
                 '--install-dir', '/tmp',
                 '--master-id', '1']
            )

            mocked_bootstrap.assert_called_once_with(
                '/tmp',
                {
                    'broken_nodes_percent': '1%',
                    'cmd': '/usr/bin/cmd'
                },
                '1'
            )

    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_configs))
    @mock.patch('treadmill.cli.admin.install.bootstrap.MasterBootstrap')
    def test_install_master_with_custom_config(self, mocked_bootstrap):
        with mock.patch.object(install,
                               '_load_configs',
                               wraps=wrap_func):
            self.runner.invoke(
                self.install_cli,
                ['--cell', '-',
                 '--zookeeper', 'zk',
                 'master',
                 '--install-dir', '/tmp',
                 '--master-id', '1',
                 '--config', 'custom1.config',
                 '--config', 'custom2.config',
                 ]
            )

            mocked_bootstrap.assert_called_once_with(
                '/tmp',
                {
                    'treadmill_cpu': '90%',
                    'cmd': '/custom/cmd'
                },
                '1'
            )

    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_configs))
    @mock.patch('treadmill.cli.admin.install.bootstrap.NodeBootstrap')
    def test_install_node_with_default_config(self, node_bootstrap):
        with mock.patch.object(install,
                               '_load_configs',
                               wraps=wrap_func):
            self.runner.invoke(
                self.install_cli,
                ['--cell', '-',
                 '--zookeeper', 'zk',
                 'node',
                 '--install-dir', '/tmp',
                 ]
            )

            node_bootstrap.assert_called_once_with(
                '/tmp',
                {
                    'treadmill_cpu': '10%',
                    'cmd': '/usr/bin/cmd'
                }
            )

    @mock.patch('builtins.open', mock.Mock(
        side_effect=_open_side_effect_for_configs))
    @mock.patch('treadmill.cli.admin.install.bootstrap.NodeBootstrap')
    def test_install_node_with_custom_config(self, mocked_bootstrap):
        with mock.patch.object(install,
                               '_load_configs',
                               wraps=wrap_func):
            self.runner.invoke(
                self.install_cli,
                ['--cell', '-',
                 '--zookeeper', 'zk',
                 'node',
                 '--install-dir', '/tmp',
                 '--config', 'custom1.config',
                 '--config', 'custom2.config',
                 ]
            )

            mocked_bootstrap.assert_called_once_with(
                '/tmp',
                {
                    'treadmill_cpu': '90%',
                    'cmd': '/custom/cmd'
                }
            )


if __name__ == '__main__':
    unittest.main()
