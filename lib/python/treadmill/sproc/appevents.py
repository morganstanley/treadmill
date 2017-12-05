"""Process application events."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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
