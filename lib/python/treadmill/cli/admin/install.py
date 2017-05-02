"""Installs and configures Treadmill locally."""
from __future__ import absolute_import

import os

import click
import yaml

import treadmill
from treadmill import bootstrap
from treadmill import cli
from treadmill import context


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--cell', required=True, envvar='TREADMILL_CELL')
    @click.option('--aliases', required=True, type=click.File(), multiple=True)
    @click.option('--config', required=False, type=click.File(), multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.pass_context
    def install(ctx, cell, aliases, config, override):
        """Installs Treadmill."""

        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell
            context.GLOBAL.resolve(cell)

        aliases_path = ":".join(
            [os.path.abspath(x.name) for x in aliases])

        ctx.obj['COMMON_DEFAULTS'] = {
            'aliases_path': aliases_path
        }

        aliases_data = {}
        for conf in aliases:
            aliases_data.update(yaml.load(conf.read()))

        ctx.obj['COMMON_DEFAULTS']['_alias'] = aliases_data
        # TODO(boysson): remove the below once all templates are cleaned up
        ctx.obj['COMMON_DEFAULTS'].update(aliases_data)

        for conf in config:
            ctx.obj['COMMON_DEFAULTS'].update(yaml.load(stream=conf))

        if override:
            ctx.obj['COMMON_DEFAULTS'].update(override)

        os.environ['TREADMILL'] = treadmill.TREADMILL
        os.environ['TREADMILL_ALIASES_PATH'] = aliases_path

    @install.command()
    @click.option('--install-dir',
                  default=lambda: os.path.join(bootstrap.DEFAULT_INSTALL_DIR,
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
                          bootstrap.DEFAULT_INSTALL_DIR,
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
                          bootstrap.DEFAULT_INSTALL_DIR,
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

        @install.command()
        @click.option('--install-dir',
                      default=lambda: os.path.join(
                          bootstrap.DEFAULT_INSTALL_DIR,
                          "treadmill_haproxy"))
        @click.option('--run/--no-run', is_flag=True, default=False)
        @click.pass_context
        def haproxy(ctx, install_dir, run):
            """Installs Treadmill haproxy."""
            haproxy_bootstrap = bootstrap.HAProxyBootstrap(
                install_dir,
                ctx.obj['COMMON_DEFAULTS']
            )

            haproxy_bootstrap.install()

            if run:
                haproxy_bootstrap.run()

        del haproxy

    return install
