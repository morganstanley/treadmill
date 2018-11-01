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

from treadmill import alert
from treadmill import appenv
from treadmill import context
from treadmill import restclient
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill import zkwatchers
from treadmill.scheduler import masterapi

_LOGGER = logging.getLogger(__name__)

# Allow 2 * count tokens to accumulate during 1 hour.
_INTERVAL = float(60 * 60)

# Delay monitoring for non-existent apps.
_DELAY_INTERVAL = float(5 * 60)


def make_alerter(alerts_dir, cell):
    """Create alert function."""

    def send_alert(instance, summary, **kwargs):
        """Send alert."""
        _LOGGER.debug('Sending alert for %s', instance)
        alert.create(
            alerts_dir, type_='monitor.suspended',
            instanceid='{}/{}'.format(cell, instance),
            summary=summary,
            **kwargs
        )

    return send_alert


def reevaluate(api_url, alert_f, state, zkclient, last_waited):
    """Evaluate state and adjust app count based on monitor"""
    # Disable too many branches/statements warning.
    #
    # pylint: disable=R0912
    # pylint: disable=R0915
    grouped = dict(state['scheduled'])
    monitors = dict(state['monitors'])

    # Do not create a copy, suspended is accessed by ref.
    suspended = state['suspended']
    waited = {}
    modified = False

    now = time.time()

    # remove outdated information in suspended dict
    extra = six.viewkeys(suspended) - six.viewkeys(monitors)
    for name in extra:
        suspended.pop(name, None)
        modified = True

    # Increase available tokens.
    for name, conf in six.iteritems(monitors):

        if suspended.get(name, 0) > now:
            _LOGGER.debug('Ignoring app %s - suspended.', name)
            continue

        # Either app is not suspended or it is past-due - remove it from
        # suspended dict.
        if suspended.pop(name, None) is not None:
            alert_f(name, 'Monitor active again', status='clear')
            modified = True

        # Max value reached, nothing to do.
        max_value = conf['count'] * 2
        available = conf['available']
        if available < max_value:
            delta = conf['rate'] * (now - conf['last_update'])
            conf['available'] = min(available + delta, max_value)

        conf['last_update'] = now

    for name, conf in six.iteritems(monitors):

        if suspended.get(name, 0) > now:
            _LOGGER.debug('Monitor is suspended for: %s.', name)
            continue

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
            _LOGGER.debug('%s => need %d, allow %d', name, needed, allowed)
            if allowed <= 0:
                # in this case available <= 0 as needed >= 1
                # we got estimated wait time, now + wait seconds
                waited[name] = now + int((1 - available) / conf['rate'])
                # new wait item, need modify
                if name not in last_waited:
                    alert_f(name, 'Monitor suspended: Rate limited')
                    modified = True

                continue

            try:
                # scheduled, remove app from waited list
                _scheduled = restclient.post(
                    [api_url],
                    '/instance/{}?count={}'.format(name, allowed),
                    payload={},
                    headers={'X-Treadmill-Trusted-Agent': 'monitor'}
                )

                if name in last_waited:
                    # this means app jump out of wait, need to clear it from zk
                    alert_f(name, 'Monitor active again', status='clear')
                    modified = True

                conf['available'] -= allowed
            except restclient.NotFoundError:
                _LOGGER.info('App not configured: %s', name)
                suspended[name] = now + _DELAY_INTERVAL
                alert_f(name, 'Monitor suspended: App not configured')
                modified = True
            except restclient.BadRequestError:
                _LOGGER.exception('Unable to start: %s', name)
                suspended[name] = now + _DELAY_INTERVAL
                alert_f(name, 'Monitor suspended: Unable to start')
                modified = True
            except restclient.ValidationError:
                _LOGGER.exception('Invalid manifest: %s', name)
                suspended[name] = now + _DELAY_INTERVAL
                alert_f(name, 'Monitor suspended: Invalid manifest')
                modified = True
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unable to create instances: %s: %s',
                                  name, needed)

        elif count < current_count:
            extra = []
            policy = conf.get('policy')
            if policy is None:
                policy = 'fifo'

            if policy == 'fifo':
                extra = grouped[name][:current_count - count]
            elif policy == 'lifo':
                extra = grouped[name][count - current_count:]
            else:
                _LOGGER.warning('Invalid scale policy: %s', policy)
                continue

            try:
                response = restclient.post(
                    [api_url], '/instance/_bulk/delete',
                    payload=dict(instances=list(extra)),
                    headers={'X-Treadmill-Trusted-Agent': 'monitor'}
                )
                _LOGGER.info('deleted: %r - %s', extra, response)

                # this means we reduce the count number, no need to wait
                modified = True

            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unable to delete instances: %r', extra)

    # total inactive means
    waited.update(suspended)
    if modified:
        _LOGGER.info('Updating suspended app monitors')
        zkutils.update(zkclient, z.path.appmonitor(), waited)

    return waited


def _run_sync(api_url, alerts_dir, once):
    """Sync app monitor count with instance count."""

    zkclient = context.GLOBAL.zk.conn

    alerter = make_alerter(alerts_dir, context.GLOBAL.cell)

    state = {
        'scheduled': {},
        'monitors': {},
        'suspended': {},
    }

    @zkclient.ChildrenWatch(z.path.scheduled())
    @utils.exit_on_unhandled
    def _scheduled_watch(children):
        """Watch scheduled instances."""
        scheduled = sorted(children)

        def _appname_fn(instancename):
            return instancename.rpartition('#')[0]

        grouped = collections.defaultdict(
            list,
            {
                k: list(v)
                for k, v in itertools.groupby(scheduled, _appname_fn)
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
                loaded = yaml.load(data)
                count = loaded['count']
                policy = loaded.get('policy')
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Invalid monitor: %s', name)
                return

            _LOGGER.info('Reconfigure monitor: %s, count: %s', name, count)
            state['monitors'][name] = {
                'count': count,
                'available': 2.0 * count,
                'last_update': time.time(),
                'policy': policy,
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

    _LOGGER.info('Ready, loading waited app list')
    last_waited = masterapi.get_suspended_appmonitors(zkclient)
    while True:
        time.sleep(1)
        last_waited = reevaluate(
            api_url, alerter, state, zkclient, last_waited
        )
        if once:
            break


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    @click.option('--api', required=True, help='Cell API url.')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--once', is_flag=True, default=False,
                  help='Run once.')
    def top(no_lock, api, approot, once):
        """Sync LDAP data with Zookeeper data."""
        tm_env = appenv.AppEnvironment(root=approot)

        if not no_lock:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _run_sync(api, tm_env.alerts_dir, once)
        else:
            _LOGGER.info('Running without lock.')
            _run_sync(api, tm_env.alerts_dir, once)

    return top
