"""Treadmill service policy monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import appenv
from treadmill import monitor


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=False)
    @click.option('-c', '--config-dir', type=click.Path(exists=True),
                  help='Config directory.', required=True)
    def run(approot, config_dir):
        """Runs monitor."""
        tm_env = None
        if approot:
            tm_env = appenv.AppEnvironment(root=approot)

        mon = monitor.Monitor(
            tm_env=tm_env,
            config_dir=config_dir
        )
        mon.run()

    return run
