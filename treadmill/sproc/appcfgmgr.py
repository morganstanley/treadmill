"""Treadmill app configurator daemon, subscribes to eventmgr events."""


import click

from .. import appcfgmgr


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def top(approot):
        """Starts appcfgmgr process."""
        mgr = appcfgmgr.AppCfgMgr(root=approot)
        mgr.run()

    return top
