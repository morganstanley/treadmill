"""Installs and configures Treadmill locally.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import admin
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
        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        if os.name == 'nt':
            wipe_script = [
                'powershell.exe', '-file',
                os.path.join(dst_dir, 'bin', 'wipe_node.ps1')
            ]
        else:
            wipe_script = os.path.join(dst_dir, 'bin', 'wipe_node.sh')

        bootstrap.wipe(
            os.path.join(dst_dir, 'wipe_me'),
            wipe_script
        )

        run_script = None
        if benchmark:
            if os.name == 'posix':
                run_script = os.path.join(dst_dir, 'bin', 'benchmark.sh')
        elif run:
            ctx.obj['PARAMS']['zookeeper'] = context.GLOBAL.zk.url
            ctx.obj['PARAMS']['ldap'] = context.GLOBAL.ldap.url
            if os.name == 'nt':
                run_script = [
                    'powershell.exe', '-file',
                    os.path.join(dst_dir, 'bin', 'run.ps1')
                ]
            else:
                admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
                cell_config = admin_cell.get(context.GLOBAL.cell)
                ctx.obj['PARAMS']['benchmark'] = cell_config.get(
                    'data', {}
                ).get('benchmark', None)
                run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        bootstrap.install(
            'node',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script,
            profile=profile,
        )

    return node
