"""Installs and configures Treadmill locally.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import bootstrap
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.option('--treadmill-id', help='Treadmill admin user.')
    @click.pass_context
    def spawn(ctx, treadmill_id, run):
        """Installs Treadmill spawn."""
        ctx.obj['PARAMS']['zookeeper'] = context.GLOBAL.zk.url
        ctx.obj['PARAMS']['ldap'] = context.GLOBAL.ldap.url

        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        bootstrap.wipe(
            os.path.join(dst_dir, 'wipe_me'),
            os.path.join(dst_dir, 'bin', 'wipe_spawn.sh')
        )

        run_script = None
        if run:
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        if treadmill_id:
            ctx.obj['PARAMS']['treadmillid'] = treadmill_id

        if not ctx.obj['PARAMS'].get('treadmillid'):
            raise click.UsageError(
                '--treadmill-id is required, '
                'unable to derive treadmill-id from context.')

        bootstrap.install(
            'spawn',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script,
            profile=profile,
        )

    return spawn
