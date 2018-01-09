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


_LOGGER = logging.getLogger(__name__)


def _wipe(wipe_me, wipe_me_sh):
    """Check if flag file is present, invoke cleanup script."""
    if os.path.exists(wipe_me):
        _LOGGER.info('Requested clean start, calling: %s', wipe_me_sh)
        os.system(wipe_me_sh)
    else:
        _LOGGER.info('Preserving data, no clean restart.')


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def haproxy(ctx, run):
        """Installs Treadmill haproxy."""
        dst_dir = ctx.obj['PARAMS']['dir']
        _wipe(
            os.path.join(dst_dir, 'wipe_me'),
            os.path.join(dst_dir, 'bin', 'wipe_haproxy.sh')
        )

        run_script = None
        if run:
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        bootstrap.install(
            'haproxy',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script
        )

    return haproxy
