"""Implementation of treadmill multi-cell monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import utils


_LOGGER = logging.getLogger(__name__)

_DEFAULT_INTERVAL = '1m'


def _count(cell, appname):
    """Get number of instances scheduled/running on the cell."""
    try:
        ctx = context.Context()
        ctx.cell = cell
        ctx.dns_domain = context.GLOBAL.dns_domain

        stateapi = ctx.state_api()
        url = '/state/?' + urllib_parse.urlencode([('match', appname)])

        response = restclient.get(stateapi, url)
        state = response.json()

        for instance in state:
            _LOGGER.info('cell: %s - %s %s %s', cell,
                         instance['name'],
                         instance['state'],
                         instance['host'])

        return len([instance for instance in state
                    if instance['state'] == 'running'])

    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Unable to get instance count for cell %s, app: %s',
                          cell, appname)
        return 0


def _configure_monitor(name, count):
    """Configure target count for the current cell."""
    _LOGGER.info('configuring monitor: %s, count: %s', name, count)
    url = '/app-monitor/%s' % name

    restapi = context.GLOBAL.cell_api()
    data = {'count': count}
    try:
        _LOGGER.debug('Creating app monitor: %s', name)
        restclient.post(restapi, url, payload=data)
    except restclient.AlreadyExistsError:
        _LOGGER.debug('Updating app monitor: %s', name)
        restclient.put(restapi, url, payload=data)


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--monitor', nargs=2, type=click.Tuple([str, int]),
                  multiple=True, required=True)
    @click.option('--once', help='Run once.', is_flag=True, default=False)
    @click.option('--interval', help='Wait interval between checks.',
                  default=_DEFAULT_INTERVAL)
    @click.argument('name')
    def controller(monitor, once, interval, name):
        """Control app monitors across cells"""
        monitors = list(monitor)

        while True:

            intended_total = 0
            actual_total = 0
            intended = 0

            for cellname, count in monitors:
                if cellname == context.GLOBAL.cell:
                    intended = count
                else:
                    actual = _count(cellname, name)

                    _LOGGER.info('state for cell %s, actual: %s, intended: %s',
                                 cellname, actual, count)

                    intended_total += count
                    actual_total += actual

            missing = intended_total - actual_total

            # If there are missing instances, start them locally. If there are
            # extra instances (missing < 0) just keep the indended state for
            # the cell.
            my_count = intended + max(0, missing)
            _LOGGER.info('intended: %s, actual: %s, missing: %s, my count: %s',
                         intended_total, actual_total, missing, my_count)

            _configure_monitor(name, my_count)

            if once:
                break

            time.sleep(utils.to_seconds(interval))

    return controller
