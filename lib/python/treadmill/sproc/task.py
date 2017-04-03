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
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def cleanup(expiration, interval, no_lock):
        """Cleans up old tasks."""

        def _cleanup():
            """Do cleanup."""
            while True:
                zk.cleanup(context.GLOBAL.zk.conn, expiration)
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

    @task.command(name='gc')
    @click.option('--max-count', help='Max non-running instance to keep.',
                  type=int,
                  default=10)
    def garbage_collect(max_count):
        """Garbage collect traces that are not active."""
        zkclient = context.GLOBAL.zk.conn
        tasks = zkclient.get_children(z.TASKS)
        for task in tasks:
            instances = sorted(zkclient.get_children(z.path.task(task)))
            fullnames = ['%s#%s' % (task, instance) for instance in instances]
            finished = [fullname for fullname in fullnames
                        if not zkclient.exists(z.path.scheduled(fullname))]

            for fullname in finished[:len(finished) - max_count]:
                _LOGGER.info('Removing finished trace: %s', fullname)
                zkutils.ensure_deleted(
                    zkclient,
                    z.path.task(fullname),
                    recursive=True
                )

    del cleanup
    del garbage_collect

    return task
