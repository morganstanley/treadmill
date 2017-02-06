"""Treadmill master scheduler."""


import click

from .. import context
from .. import master
from .. import scheduler


def init():
    """Return top level command handler."""

    @click.command()
    @click.argument('events-dir', type=click.Path(exists=True))
    def run(events_dir):
        """Run Treadmill master scheduler."""
        scheduler.DIMENSION_COUNT = 3
        cell_master = master.Master(context.GLOBAL.zk.conn,
                                    context.GLOBAL.cell,
                                    events_dir)
        cell_master.run()

    return run
