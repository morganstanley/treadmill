"""Syncronizes cell Zookeeper with LDAP data."""
from __future__ import absolute_import

import logging
import os
import time
import itertools
import collections

import click
import ldap3

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

            count = data.get('count')
            if count is None:
                _LOGGER.warn('Invalid monitor spec: %s', appname)
                continue

            current_count = len(grouped[appname])
            _LOGGER.debug('App: %s current: %s, target %s',
                          appname, current_count, count)
            if count == current_count:
                continue

            if count > current_count:
                # need to start more.
                needed = count - current_count
                try:
                    scheduled = instance_api.create(appname, {}, count=needed)
                    # TODO: may need to rationalize this and not expose low
                    #       level ldap exception from admin.py, and rather
                    #       return None for non-existing entities.
                except ldap3.LDAPNoSuchObjectResult:
                    _LOGGER.warn('Application not configured: %s',
                                 appname)
                except Exception:  # pylint: disable=W0703
                    _LOGGER.exception('Unable to create instances: %s: %s',
                                      appname, needed)

            if count < current_count:
                for extra in grouped[appname][:current_count - count]:
                    try:
                        instance_api.delete(extra)
                    except Exception:  # pylint: disable=W0703
                        _LOGGER.exception('Unable to delete instance: %s',
                                          extra)

        # TODO: need to send alert that monitor failed.
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
