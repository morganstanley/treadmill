"""Treadmill events publisher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import context
from treadmill import zkutils

from treadmill.trace import events_publisher


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--app-events-dir', type=click.Path(exists=True))
    @click.option('--server-events-dir', type=click.Path(exists=True))
    def run(app_events_dir, server_events_dir):
        """Run events publisher."""
        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_lost)

        publisher = events_publisher.EventsPublisher(
            zkclient,
            app_events_dir=app_events_dir,
            server_events_dir=server_events_dir
        )
        publisher.run()

    return run
