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
    @click.pass_context
    def master(ctx, run):
        """Installs Treadmill master."""

        ctx.obj['PARAMS']['zookeeper'] = context.GLOBAL.zk.url
        ctx.obj['PARAMS']['ldap'] = context.GLOBAL.ldap.url
        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        run_sh = None
        if run:
            run_sh = os.path.join(dst_dir, 'treadmill', 'bin', 'run.sh')

        bootstrap.install(
            'master',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_sh,
            profile=profile,
        )

    return master
