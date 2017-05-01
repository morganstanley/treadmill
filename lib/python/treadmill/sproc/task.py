"""Cleans up old tasks from Treadmill."""
from __future__ import absolute_import

import logging
import time

import click

from treadmill.apptrace import zk
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

# Interval between cleanup - every hour.
TASK_CHECK_INTERVAL = 60 * 60


def init():
    """Top level command handler."""

    @click.group()
    def task():
        """Manage Treadmill tasks."""
        pass

    @task.command()
    @click.option('--interval', help='Timeout between checks (sec).',
                  default=TASK_CHECK_INTERVAL)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def cleanup(interval, no_lock):
        """Cleans up old tasks."""

        def _cleanup():
            """Do cleanup."""
            while True:
                zk.cleanup(context.GLOBAL.zk.conn)
                _LOGGER.info('Finished cleanup, sleep %s sec', interval)
                time.sleep(interval)

        if no_lock:
            _cleanup()
        else:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _cleanup()

    del cleanup
    return task
