"""Runs the Treadmill container cleanup job.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cleanup


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
        cleaner = cleanup.Cleanup(approot)
        cleaner.run()

    @cleanup_grp.command('instance')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.argument('instance', nargs=1)
    def cleanup_instance(approot, runtime, instance):
        """Actually do the cleanup of the instance.
        """
        cleaner = cleanup.Cleanup(approot)
        cleaner.invoke(runtime, instance)

    del cleanup_watcher
    del cleanup_instance
    return cleanup_grp
