"""Installs and configures Treadmill keytab fwd locally.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging

import click

from treadmill.bootstrap import install as bs_install


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler.
    """

    @click.command(name='kt-fwd')
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def kt_fwd(ctx, run):
        """Installs Treadmill keytab fwd server.
        """
        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        run_script = None
        if run:
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        bs_install.install(
            'kt-fwd',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_script,
            profile=profile,
        )

    return kt_fwd
