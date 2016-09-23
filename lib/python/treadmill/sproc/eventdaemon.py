"""Treadmill event daemon, subscribes to scheduler events."""
from __future__ import absolute_import

import click

from .. import eventmgr


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def eventdaemon(approot):
        """Listens to Zookeeper events."""
        evmgr = eventmgr.EventMgr(root=approot)
        evmgr.run()

    return eventdaemon
