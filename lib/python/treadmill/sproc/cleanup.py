"""Runs the Treadmill container cleanup job.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import appenv
from treadmill import cleanup
from treadmill import cli
from treadmill import utils


def init():
    """Top level command handler."""

    @click.group(name='cleanup')
    def cleanup_grp():
        """Cleanup click group."""

    @cleanup_grp.command('watcher')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def cleanup_watcher(approot):
        """Start cleanup watcher."""
        tm_env = appenv.AppEnvironment(root=approot)
        cleaner = cleanup.Cleanup(tm_env)
        cleaner.run()

    @cleanup_grp.command('instance')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.option('--runtime-param', type=cli.LIST, required=False)
    @click.argument('instance', nargs=1)
    def cleanup_instance(approot, runtime, instance, runtime_param):
        """Actually do the cleanup of the instance.
        """
        param = utils.equals_list2dict(runtime_param or [])

        tm_env = appenv.AppEnvironment(root=approot)
        cleaner = cleanup.Cleanup(tm_env)
        cleaner.invoke(runtime, instance, param)

    del cleanup_watcher
    del cleanup_instance
    return cleanup_grp
