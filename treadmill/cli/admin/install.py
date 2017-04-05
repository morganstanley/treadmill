"""Installs and configures Treadmill locally."""

import os

import click
import yaml

import treadmill

from treadmill import context
from treadmill.osmodules import bootstrap
from treadmill import cli


def _load_configs(config, default_file, ctx):
    if not config:
        config = [open(treadmill.TREADMILL + '/etc/linux.exe.config'),
                  open(treadmill.TREADMILL + default_file)]

    ctx.obj['COMMON_DEFAULTS'] = {}
    for _file in config:
        yml = yaml.load(_file)
        ctx.obj['COMMON_DEFAULTS'].update(yml)


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--cell', required=True, envvar='TREADMILL_CELL')
    @click.option('--zookeeper', required=True, envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt)
    @click.pass_context
    def install(ctx, cell, zookeeper):
        """Installs Treadmill."""
        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell
            context.GLOBAL.resolve(cell)

    @install.command()
    @click.option('--install-dir',
                  default=lambda: os.path.join(bootstrap.default_install_dir(),
                                               "treadmill"))
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.option('--config', type=click.File(), multiple=True)
    @click.pass_context
    def node(ctx, install_dir, run, config):
        node_config = '/local/linux/node.config.yml'
        _load_configs(config, node_config, ctx)

        """Installs Treadmill node."""
        node_bootstrap = bootstrap.NodeBootstrap(
            install_dir,
            ctx.obj['COMMON_DEFAULTS']
        )

        node_bootstrap.install()

        if run:
            node_bootstrap.run()

    del node

    if os.name != 'nt':
        @install.command()
        @click.option('--install-dir',
                      default=lambda: os.path.join(
                          bootstrap.default_install_dir(),
                          "treadmill_master"))
        @click.option('--run/--no-run', is_flag=True, default=False)
        @click.option('--master-id', required=True,
                      type=click.Choice(['1', '2', '3']))
        @click.option('--config', type=click.File(), multiple=True)
        @click.pass_context
        def master(ctx, install_dir, run, master_id, config):
            """Installs Treadmill master."""

            master_config_file = '/local/linux/master.config.yml'

            _load_configs(config, master_config_file, ctx)

            master_bootstrap = bootstrap.MasterBootstrap(
                install_dir,
                ctx.obj['COMMON_DEFAULTS'],
                master_id
            )
            master_bootstrap.install()

            if run:
                master_bootstrap.run()

        del master

    return install
