"""Syncronizes cell Zookeeper with LDAP data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import cli
from treadmill import context
from treadmill import plugin_manager
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def _run_sync(cellsync_plugins, once):
    """Sync Zookeeper with LDAP, runs with lock held.
    """
    while True:
        # Sync app groups
        if not cellsync_plugins:
            cellsync_plugins = plugin_manager.names('treadmill.cellsync')
        for name in cellsync_plugins:
            try:
                plugin = plugin_manager.load('treadmill.cellsync', name)
                plugin()
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Error processing sync plugin: %s', name)

        if once:
            return

        time.sleep(60)


def init():
    """Return top level command handler.
    """

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    @click.option('--sync-plugins', default=None, type=cli.LIST,
                  help='List of plugins to run.')
    @click.option('--once', is_flag=True, default=False,
                  help='Run once.')
    def top(no_lock, sync_plugins, once):
        """Sync LDAP data with Zookeeper data.
        """
        if not no_lock:
            _LOGGER.info('Waiting for leader lock.')
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            with lock:
                _run_sync(sync_plugins, once)
        else:
            _LOGGER.info('Running without lock.')
            _run_sync(sync_plugins, once)

    return top
