"""Syncronizes cell Zookeeper with LDAP data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import itertools
import logging
import math
import time

import click

import six

from treadmill import context
from treadmill import restclient
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill import zkwatchers

_LOGGER = logging.getLogger(__name__)

# Allow 2 * count tokens to accumulate during 1 hour.
_INTERVAL = float(60 * 60)


def reevaluate(api_url, state):
    """Evaluate state and adjust app count based on monitor"""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912

    grouped = dict(state['scheduled'])
    monitors = dict(state['monitors'])
    now = time.time()

    # Increase available tokens.
    for name, conf in monitors.items():
        # Max value reached, nothing to do.
        max_value = conf['count'] * 2
        available = conf['available']
        if available < max_value:
            delta = conf['rate'] * (now - conf['last_update'])
            conf['available'] = min(available + delta, max_value)
        conf['last_update'] = now

    # Allow every application to evaluate
    success = True

    for name, conf in monitors.items():

        count = conf['count']
        available = conf['available']

        current_count = len(grouped.get(name, []))
        _LOGGER.debug('App: %r current: %d, target %d',
                      name, current_count, count)

        if count == current_count:
            continue

        elif count > current_count:
            needed = count - current_count
            allowed = int(min(needed, math.floor(available)))
            if allowed <= 0:
                continue

            try:
                _scheduled = restclient.post(
                    [api_url],
                    '/instance/{}?count={}'.format(name, allowed),
                    payload={},
                    headers={'X-Treadmill-Trusted-Agent': 'monitor'}
                )
                conf['available'] -= allowed

            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unable to create instances: %s: %s',
                                  name, needed)

        elif count < current_count:
            extra = grouped[name][:current_count - count]
            try:
                response = restclient.post(
                    [api_url], '/instance/_bulk/delete',
                    payload=dict(instances=list(extra)),
                    headers={'X-Treadmill-Trusted-Agent': 'monitor'}
                )
                _LOGGER.info('deleted: %r - %s', extra, response)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unable to delete instances: %r', extra)

    return success


def _run_sync(api_url):
    """Sync app monitor count with instance count."""

    zkclient = context.GLOBAL.zk.conn

    state = {
        'scheduled': {},
        'monitors': {}
    }

    @zkclient.ChildrenWatch(z.path.scheduled())
    @utils.exit_on_unhandled
    def _scheduled_watch(children):
        """Watch scheduled instances."""
        scheduled = sorted(children)
        grouped = collections.defaultdict(
            list,
            {
                k: list(v)
                for k, v in itertools.groupby(
                    scheduled,
                    lambda n: n.rpartition('#')[0]
                )
            }
        )
        state['scheduled'] = grouped
        return True

    def _watch_monitor(name):
        """Watch monitor."""

        # Establish data watch on each monitor.
        @zkwatchers.ExistingDataWatch(zkclient, z.path.appmonitor(name))
        @utils.exit_on_unhandled
        def _monitor_data_watch(data, stat, event):
            """Monitor individual monitor."""
            if (event is not None and event.type == 'DELETED') or stat is None:
                _LOGGER.info('Removing watch on deleted monitor: %s', name)
                return

            try:
                count = yaml.load(data)['count']
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Invalid monitor: %s', name)
                return

            _LOGGER.info('Reconfigure monitor: %s, count: %s', name, count)
            state['monitors'][name] = {
                'count': count,
                'available': 2.0 * count,
                'last_update': time.time(),
                'rate': (2.0 * count / _INTERVAL)
            }

    @zkclient.ChildrenWatch(z.path.appmonitor())
    @utils.exit_on_unhandled
    def _appmonitors_watch(children):
        """Watch app monitors."""

        monitors = set(children)
        extra = six.viewkeys(state['monitors']) - monitors
        for name in extra:
            _LOGGER.info('Removing extra monitor: %r', name)
            if state['monitors'].pop(name, None) is None:
                _LOGGER.warning(
                    'Failed to remove non-existent monitor: %r', name
                )

        missing = monitors - six.viewkeys(state['monitors'])

        for name in missing:
            _LOGGER.info('Adding missing monitor: %s', name)
            _watch_monitor(name)

    _LOGGER.info('Ready')

    while True:
        time.sleep(1)
        if not reevaluate(api_url, state):
            _LOGGER.error('Unhandled exception while evaluating state.')
            break


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    @click.option('--api', required=True, help='Cell API url.')
    def top(no_lock, api):
        """Sync LDAP data with Zookeeper data."""
        if not no_lock:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _run_sync(api)
        else:
            _LOGGER.info('Running without lock.')
            _run_sync(api)

    return top
