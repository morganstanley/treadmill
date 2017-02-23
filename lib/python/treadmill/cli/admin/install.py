"""Installs and configures Treadmill locally."""
from __future__ import absolute_import

import os

import click
import yaml

from treadmill import cli
from treadmill import context
from treadmill.osmodules import bootstrap


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--cell', required=True, envvar='TREADMILL_CELL')
    @click.option('--config', required=True, type=click.File(), multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.pass_context
    def install(ctx, cell, config, override):
        """Installs Treadmill."""

        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell
            context.GLOBAL.resolve(cell)

        ctx.obj['COMMON_DEFAULTS'] = {}

        for conf in config:
            ctx.obj['COMMON_DEFAULTS'].update(yaml.load(conf.read()))

        if override:
            ctx.obj['COMMON_DEFAULTS'].update(override)

    @install.command()
    @click.option('--install-dir',
                  default=lambda: os.path.join(bootstrap.default_install_dir(),
                                               "treadmill"))
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def node(ctx, install_dir, run):
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
        @click.pass_context
        def master(ctx, install_dir, run, master_id):
            """Installs Treadmill master."""
            master_bootstrap = bootstrap.MasterBootstrap(
                install_dir,
                ctx.obj['COMMON_DEFAULTS'],
                master_id
            )

            master_bootstrap.install()

            if run:
                master_bootstrap.run()

        del master

        @install.command()
        @click.option('--install-dir',
                      default=lambda: os.path.join(
                          bootstrap.default_install_dir(),
                          "treadmill_spawn"))
        @click.option('--run/--no-run', is_flag=True, default=False)
        @click.pass_context
        def spawn(ctx, install_dir, run):
            """Installs Treadmill spawn."""
            spawn_bootstrap = bootstrap.SpawnBootstrap(
                install_dir,
                ctx.obj['COMMON_DEFAULTS']
            )

            spawn_bootstrap.install()

            if run:
                spawn_bootstrap.run()

        del spawn

    return install
