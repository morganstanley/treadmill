"""Syncronizes cell Zookeeper with LDAP data."""
from __future__ import absolute_import

import logging
import os
import time
import itertools
import collections

import click

from treadmill import context
from treadmill import sysinfo
from treadmill import authz
from treadmill import master
from treadmill.api import instance


_LOGGER = logging.getLogger(__name__)


def _run_sync():
    """Sync app monitor count with instance count."""

    instance_api = instance.init(authz.NullAuthorizer())
    zkclient = context.GLOBAL.zk.conn

    while True:
        scheduled = sorted(master.list_scheduled_apps(zkclient))
        appname_f = lambda n: n[:n.find('#')]
        grouped = collections.defaultdict(
            list,
            {k: list(v) for k, v in itertools.groupby(scheduled, appname_f)}
        )

        appmonitors = master.appmonitors(zkclient)
        for appname in appmonitors:
            data = master.get_appmonitor(zkclient, appname)
            if not data:
                _LOGGER.info('App monitor does not exist: %s', appname)
                continue

            count = data['count']
            current_count = len(grouped[appname])
            _LOGGER.debug('App: %s current: %s, target %s',
                          appname, current_count, count)
            if count == current_count:
                continue

            if count > current_count:
                # need to start more.
                needed = count - current_count
                scheduled = instance_api.create(appname, {}, count=needed)

            if count < current_count:
                for extra in grouped[appname][:current_count - count]:
                    instance_api.delete(extra)

        time.sleep(60)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def top(no_lock):
        """Sync LDAP data with Zookeeper data."""
        context.GLOBAL.zk.conn.ensure_path('/appmonitor-election')
        me = '%s.%d' % (sysinfo.hostname(), os.getpid())
        lock = context.GLOBAL.zk.conn.Lock('/appmonitor-election', me)
        if not no_lock:
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _run_sync()
        else:
            _LOGGER.info('Running without lock.')
            _run_sync()

    return top
