"""Treadmill LBVirtual checkout.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import admin
from treadmill import checkout
from treadmill import cli
from treadmill import context
from treadmill import discovery
from treadmill import plugin_manager

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbendpoint


_LOGGER = logging.getLogger(__name__)

_CHECK_INTERVAL = 5 * 60


def _check_state(host, port):
    if checkout.connect(host, port):
        return 'up'
    return 'down'


def _check_member(hostport):
    host, port = hostport.split(':')
    return _check_state(host, int(port))


def _check_virtual(virtual):
    host, port = virtual.split('.0.')
    return _check_state(host, int(port))


def _check_lbendpoint(lbe, cell, zkclient):
    lbe_errors = []

    _LOGGER.info('Checking LBEndpoint %s', lbe['_id'])

    virtuals = lbendpoint.filter_cell_virtuals(lbe['virtuals'], [cell])
    for virtual in virtuals:
        if _check_virtual(virtual) == 'up':
            _LOGGER.info('Virtual %s is up', virtual)
        else:
            _LOGGER.info('Virtual %s is down, checking members', virtual)

            discovery_iter = discovery.iterator(
                zkclient, lbe['pattern'], lbe['endpoint'], watch=False
            )

            members = {}
            for (endpoint, hostport) in discovery_iter:
                if ':tcp:' in endpoint:
                    state = _check_member(hostport)
                    members[(endpoint, hostport)] = state
                    _LOGGER.info('%s on %s is %s', endpoint, hostport, state)
            if 'up' in members.values():
                lbe_errors.append((virtual, members))
                _LOGGER.info('Virtual %s is down but has up members', virtual)
    return lbe_errors


def check(environment, cell, zkclient, admin_app_group):
    """Check LBEndpoints/Virtuals."""
    errors = []

    app_groups = admin_app_group.list({
        'group-type': 'lbendpoint',
    })

    for group in app_groups:
        lbe = lbendpoint.group2lbendpoint(group)

        if environment != lbe['environment']:
            _LOGGER.debug('Skipping LBEndpoint %s, environment: %s',
                          lbe['_id'], lbe['environment'])
            continue

        if cell not in lbe['cells']:
            _LOGGER.debug('Skipping LBEndpoint %s, cells: %r',
                          lbe['_id'], lbe['cells'])
            continue

        lbe_errors = _check_lbendpoint(lbe, cell, zkclient)
        if lbe_errors:
            errors.append((lbe['_id'], lbe_errors))

    return errors


def init():
    """Top level command handler."""
    @click.command()
    @click.option('--environment', help='Checkout environment.',
                  required=True, envvar='TREADMILL_ENV')
    @click.option('--interval', help='Timeout between checks (sec).',
                  type=int, default=_CHECK_INTERVAL)
    @click.option('--processor', help='Result processing plugin.',
                  type=cli.LIST)
    def lbvirtual_checkout(environment, interval, processor):
        """Run LBVirtual checkout."""
        cell = context.GLOBAL.cell
        zkclient = context.GLOBAL.zk.conn
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)

        if environment != 'prod':
            environment = 'dev'

        processors = [
            plugin_manager.load('treadmill.lbvirtual.checkout.processors', mod)
            for mod in processor or []
        ]

        while True:
            try:
                _LOGGER.info('Starting checkout, environment: %s', environment)
                start_time = time.time()
                errors = check(environment, cell, zkclient, admin_app_group)
                _LOGGER.info('Checkout time: %s, errors: %r',
                             time.time() - start_time, errors)
                for plugin in processors:
                    plugin.process(environment, cell, errors)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('lbvirtual_checkout error')

            time.sleep(interval)

    return lbvirtual_checkout
