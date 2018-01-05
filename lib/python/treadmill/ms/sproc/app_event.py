"""Treadmill app-event daemon.

Send out container event interested to Watchtower
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import context
from treadmill import zkutils
from treadmill import zknamespace as z
from treadmill.zksync import utils as zksync_utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import app_event

_LOGGER = logging.getLogger(__name__)


def init():
    """Treadmill App Event"""

    @click.command(name='app-event')
    @click.option('--fs-root',
                  help='Root file system directory to zk2fs',
                  required=True)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    @click.option('--before-hours', type=int, default=12,
                  help='send sow event since X hours ago when launched')
    @click.option('--host', default='localhost',
                  help='Watchtower collecotor host address')
    @click.option('--port', type=int, default=13684,
                  help='Watchtower collecotor port')
    @click.option('--once', help='Sync once and exit.',
                  is_flag=True, default=False)
    def appevent(fs_root, no_lock, before_hours, host, port, once):
        """ Launch app event service to send events to Watchtower """

        cell = context.GLOBAL.cell
        since = time.time() - before_hours * 3600
        event_emitter = app_event.EventEmitter(
            cell, fs_root, host, port, since=since
        )

        # keep sleeping until zksync ready
        zksync_utils.wait_for_ready(fs_root)

        if not no_lock:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))

            _LOGGER.info('Waiting for leader lock.')
            with lock:
                event_emitter.run(once=once)
        else:
            _LOGGER.info('Running without lock.')
            event_emitter.run(once=once)

    return appevent
