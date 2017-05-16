"""Installs and configures Treadmill locally."""
from __future__ import absolute_import

import os
import logging

import click

import treadmill
from treadmill import bootstrap

if os.name != 'nt':
    from treadmill.spawn import tree as spawn_tree


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def spawn(ctx, run):
        """Installs Treadmill spawn."""
        dst_dir = ctx.obj['PARAMS']['dir']

        bootstrap.wipe(
            os.path.join(dst_dir, 'wipe_me'),
            os.path.join(dst_dir, 'bin', 'wipe_spawn.sh')
        )

        run_script = None
        if run:
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        spawn_tree.Tree(dst_dir).create()
        bootstrap.install(
            os.path.join(treadmill.TREADMILL, 'local', 'linux', 'spawn'),
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script
        )

    return spawn
