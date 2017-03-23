"""Cleans up old tasks from Treadmill."""


import logging
import time

import click

from treadmill.apptrace import zk
from treadmill import sysinfo
from treadmill import context


_LOGGER = logging.getLogger(__name__)

# Delete all nodes older than 1 day
TASK_EXPIRATION_TIME = 60 * 60 * 24

# Interval between cleanup - every hour.
TASK_CHECK_INTERFAL = 60 * 60


def init():
    """Top level command handler."""

    @click.group()
    def task():
        """Manage Treadmill tasks."""
        pass

    @task.command()
    @click.option('--expiration', help='Task expiration (sec).',
                  default=TASK_EXPIRATION_TIME)
    @click.option('--interval', help='Timeout between checks (sec).',
                  default=TASK_CHECK_INTERFAL)
    def cleanup(expiration, interval):
        """Cleans up old tasks."""
        context.GLOBAL.zk.conn.ensure_path('/task-cleanup-election')
        me = '%s' % (sysinfo.hostname())
        lock = context.GLOBAL.zk.conn.Lock('/task-cleanup-election', me)
        _LOGGER.info('Waiting for leader lock.')
        with lock:
            while True:
                zk.cleanup(context.GLOBAL.zk.conn, expiration)
                _LOGGER.info('Finished cleanup, sleep %s sec',
                             interval)
                time.sleep(interval)

    del cleanup
    return task
