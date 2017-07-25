"""Installs and configures Treadmill locally."""
from __future__ import absolute_import

import os
import logging

import click

from treadmill import bootstrap
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.option('--benchmark/--no-benchmark', is_flag=True, default=False)
    @click.pass_context
    def node(ctx, run, benchmark):
        """Installs Treadmill node."""

        ctx.obj['PARAMS']['zookeeper'] = context.GLOBAL.zk.url
        ctx.obj['PARAMS']['ldap'] = context.GLOBAL.ldap.url

        params = ctx.obj['PARAMS']
        dst_dir = params['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        if os.name == 'nt':
            wipe_script = os.path.join(dst_dir, 'bin', 'wipe_node.cmd')
        else:
            wipe_script = os.path.join(dst_dir, 'bin', 'wipe_node.sh')

        bootstrap.wipe(
            os.path.join(dst_dir, 'wipe_me'),
            wipe_script
        )

        run_script = None

        if benchmark and os.name != 'nt':
            run_script = os.path.join(dst_dir, 'bin', 'benchmark.sh')

        if run:
            if os.name == 'nt':
                run_script = os.path.join(dst_dir, 'bin', 'run.cmd')
            else:
                run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        bootstrap.install(
            'node',
            dst_dir,
            params,
            run=run_script,
            profile=profile,
        )

    return node
