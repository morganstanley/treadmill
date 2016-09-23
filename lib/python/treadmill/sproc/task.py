"""Cleans up old tasks from Treadmill."""
from __future__ import absolute_import

import logging
import time

import click

from .. import apptrace
from .. import sysinfo
from .. import context


_LOGGER = logging.getLogger(__name__)

# Delete all nodes older than 1 day
TASK_EXPIRATION_TIME = 60 * 60 * 24


def init():
    """Top level command handler."""

    @click.group()
    def task():
        """Manage Treadmill tasks."""
        pass

    @task.command()
    def cleanup():
        """Cleans up old tasks."""
        context.GLOBAL.zk.conn.ensure_path('/task-cleanup-election')
        me = '%s' % (sysinfo.hostname())
        lock = context.GLOBAL.zk.conn.Lock('/task-cleanup-election', me)
        _LOGGER.info('Waiting for leader lock.')
        with lock:
            while True:
                apptrace.cleanup(context.GLOBAL.zk.conn, TASK_EXPIRATION_TIME)
                logging.info('Finished cleanup, sleep %s sec',
                             TASK_EXPIRATION_TIME)
                time.sleep(TASK_EXPIRATION_TIME)

    del cleanup
    return task
