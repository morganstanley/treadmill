"""Treadmill cron.

This system process uses a zookeeper data storage to read cron data and
act on the events. The following events should be supported:

    1. Application: start and stop
    2. Monitor: set count
    3. Allocation: disable/enable allocations
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from twisted.internet import reactor

from treadmill import context
from treadmill import cron
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def _do_watch(zkclient):
    """Actually do the children watch"""
    scheduler = cron.get_scheduler(zkclient)

    @zkclient.ChildrenWatch(z.CRON_JOBS)
    @utils.exit_on_unhandled
    def _new_cron_jobs(_children):
        """Children watch on new cron jobs"""
        _LOGGER.info(
            'Waking up the job scheduler, as children have changed'
        )
        scheduler.wakeup()


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def run(no_lock):
        """Run Treadmill master scheduler."""
        zkclient = context.GLOBAL.zk.conn
        zkclient.ensure_path(z.CRON_JOBS)

        if no_lock:
            _do_watch(zkclient)
            reactor.run()
        else:
            lock = zkutils.make_lock(
                zkclient, z.path.election(__name__)
            )
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _do_watch(zkclient)
                reactor.run()

    return run
