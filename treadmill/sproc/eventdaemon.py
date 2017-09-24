"""Treadmill event daemon, subscribes to scheduler events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import eventmgr


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
