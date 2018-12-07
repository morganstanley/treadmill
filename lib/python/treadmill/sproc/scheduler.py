"""Treadmill master scheduler."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import context
from treadmill import scheduler
from treadmill.scheduler import master
from treadmill.scheduler import zkbackend


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--once', is_flag=True, default=False,
                  help='Run once.')
    @click.option('--app-events-dir', type=click.Path(exists=True))
    @click.option('--server-events-dir', type=click.Path(exists=True))
    def run(once, app_events_dir, server_events_dir):
        """Run Treadmill master scheduler."""
        scheduler.DIMENSION_COUNT = 3
        cell_master = master.Master(
            zkbackend.ZkBackend(context.GLOBAL.zk.conn),
            context.GLOBAL.cell,
            app_events_dir,
            server_events_dir
        )
        cell_master.run(once)

    return run
