"""Process application events."""


import click

from .. import appevents
from .. import context
from .. import zkutils


def init():
    """App main."""

    @click.command(name='appevents')
    @click.argument('appevents-dir', type=click.Path(exists=True))
    def appevents_cmd(appevents_dir):
        """Publish application events."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)
        watcher = appevents.AppEventsWatcher(context.GLOBAL.zk.conn,
                                             appevents_dir)
        watcher.run()

    return appevents_cmd
