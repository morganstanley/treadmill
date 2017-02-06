"""Syncronizes cell Zookeeper with LDAP data."""


import logging
import os
import time
import itertools
import collections

import click
import ldap3
import yaml

from treadmill import context
from treadmill import exc
from treadmill import sysinfo
from treadmill import authz
from treadmill import zknamespace as z
from treadmill.api import instance


_LOGGER = logging.getLogger(__name__)


def reevaluate(instance_api, state):
    """Evaluate state and adjust app count."""

    grouped = dict(state['scheduled'])
    monitors = dict(state['monitors'])

    for name, count in monitors.items():

        current_count = len(grouped.get(name, []))
        _LOGGER.debug('App: %s current: %s, target %s',
                      name, current_count, count)

        if count == current_count:
            continue

        if count > current_count:
            # need to start more.
            needed = count - current_count
            try:
                instance_api.create(name, {}, count=needed)
                # TODO: may need to rationalize this and not expose low
                #       level ldap exception from admin.py, and rather
                #       return None for non-existing entities.
            except ldap3.LDAPNoSuchObjectResult:
                _LOGGER.warn('Application not configured: %s',
                             name)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unable to create instances: %s: %s',
                                  name, needed)

        if count < current_count:
            for extra in grouped[name][:current_count - count]:
                try:
                    instance_api.delete(extra)
                except Exception:  # pylint: disable=W0703
                    _LOGGER.exception('Unable to delete instance: %s',
                                      extra)


def _run_sync():
    """Sync app monitor count with instance count."""

    instance_api = instance.init(authz.NullAuthorizer())
    zkclient = context.GLOBAL.zk.conn

    state = {
        'scheduled': {},
        'monitors': {}
    }

    @zkclient.ChildrenWatch(z.path.scheduled())
    @exc.exit_on_unhandled
    def _scheduled_watch(children):
        """Watch scheduled instances."""
        scheduled = sorted(children)
        appname_f = lambda n: n[:n.find('#')]
        grouped = collections.defaultdict(
            list,
            {k: list(v) for k, v in itertools.groupby(scheduled, appname_f)}
        )
        state['scheduled'] = grouped
        reevaluate(instance_api, state)
        return True

    def _watch_monitor(name):
        """Watch monitor."""

        # Establish data watch on each monitor.
        @zkclient.DataWatch(z.path.appmonitor(name))
        @exc.exit_on_unhandled
        def _monitor_data_watch(data, _stat, event):
            """Monitor individual monitor."""
            if (event and event.type == 'DELETED') or (data is None):
                try:
                    del state['monitors'][name]
                except KeyError:
                    pass

                _LOGGER.info('Removing watch on deleted monitor: %s', name)
                return False

            try:
                count = yaml.load(data)['count']
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Invalid monitor: %s', name)
                return False

            _LOGGER.info('Reconfigure monitor: %s, count: %s', name, count)
            state['monitors'][name] = count
            reevaluate(instance_api, state)
            return True

    @zkclient.ChildrenWatch(z.path.appmonitor())
    @exc.exit_on_unhandled
    def _appmonitors_watch(children):
        """Watch app monitors."""

        monitors = set(children)
        extra = set(state['monitors'].keys()) - monitors
        for name in extra:
            _LOGGER.info('Removing extra monitor: %s', name)
            del state['monitors'][name]

        missing = monitors - set(state['monitors'].keys())

        for name in missing:
            _LOGGER.info('Adding missing monitor: %s', name)
            _watch_monitor(name)

    _LOGGER.info('Ready')

    while True:
        time.sleep(6000)


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
