"""Treadmill app configurator daemon, subscribes to eventmgr events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import appcfgmgr


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    def run(approot, runtime):
        """Starts appcfgmgr process."""
        mgr = appcfgmgr.AppCfgMgr(approot, runtime)
        mgr.run()

    return run
