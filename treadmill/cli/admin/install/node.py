"""Installs and configures Treadmill locally."""
from __future__ import absolute_import

import os
import logging
import glob

import click

from treadmill import bootstrap
from treadmill import osnoop


_LOGGER = logging.getLogger(__name__)


@osnoop.windows
def _set_env(dst_dir):
    """Sets TREADMILL_ environment variables"""
    env_files = glob.glob(os.path.join(dst_dir, 'env', '*'))
    for env_file in env_files:
        with open(env_file, 'r') as f:
            env = f.readline()
            if env:
                env = env.strip()
        os.environ[str(os.path.basename(env_file))] = env


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.pass_context
    def node(ctx, run):
        """Installs Treadmill node."""
        params = ctx.obj['PARAMS']
        dst_dir = params['dir']
        if os.name == 'nt':
            wipe_script = os.path.join(dst_dir, 'bin', 'wipe_node.cmd')
        else:
            wipe_script = os.path.join(dst_dir, 'bin', 'wipe_node.sh')

        bootstrap.wipe(
            os.path.join(dst_dir, 'wipe_me'),
            wipe_script
        )

        run_script = None
        if run and os.name != 'nt':
            run_script = os.path.join(dst_dir, 'bin', 'run.sh')

        bootstrap.install(
            'node',
            dst_dir,
            params,
            run=run_script
        )

        # TODO: There is huge assymetry here, need to think how to
        #       resolve this.
        if os.name == 'nt':
            run_script = os.path.join(dst_dir, 'bin', 'run.cmd')
            cmd = bootstrap.interpolate('{{ s6 }}\\winss-svscan.exe', params)
            arg = bootstrap.interpolate('{{ dir }}\\init', params)
            _set_env(dst_dir)
            # needed for winss-svscan
            os.chdir(arg)
            os.execvp(cmd, [arg])

    return node
