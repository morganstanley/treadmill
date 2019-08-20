"""Installs and configures Treadmill tkt-fwd locally.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import os
import logging
import shutil

import click

from treadmill.bootstrap import install as bs_install


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler.
    """

    @click.command(name='tkt-fwd')
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def tkt_fwd(ctx, run):
        """Installs Treadmill tkt-fwd server.
        """
        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        run_script = None
        if run:
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        locker_scandir = os.path.join(dst_dir, 'lockers', '*')
        for locker in glob.glob(locker_scandir):
            _LOGGER.info('Removing: %s', locker)
            shutil.rmtree(locker)

        bs_install.install(
            'tkt-fwd',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script,
            profile=profile,
        )

    return tkt_fwd
