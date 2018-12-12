"""Treadmill Application monitor CLI

Create, delete and manage app monitors.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging

import click
from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient


_LOGGER = logging.getLogger(__name__)

_EXCEPTIONS = []
_EXCEPTIONS.extend(restclient.CLI_REST_EXCEPTIONS)

_ON_EXCEPTIONS = cli.handle_exceptions(_EXCEPTIONS)

_REST_PATH = '/app-monitor/'


def _check_configure_usage(count):
    """Checks options constraints for configure verb."""
    if count is None:
        raise click.UsageError('Require --count on configure creation')


def init():  # pylint: disable=R0912
    """Configures application monitor"""
    formatter = cli.make_formatter('app-monitor')

    @click.group()
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def monitor_group():
        """Manage Treadmill app monitor configuration.
        """

    @monitor_group.command()
    @click.option('-n', '--count', type=int, help='Instance count')
    @click.option('-p', '--policy', type=click.Choice(['fifo', 'lifo']),
                  help='Instance scale policy: fifo (remove oldest first), '
                       'lifo (remove latest first)')
    @click.argument('name')
    @_ON_EXCEPTIONS
    def configure(count, name, policy):
        """Configure application monitor"""

        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + name

        options = {}
        if count is not None:
            options['count'] = count
        if policy is not None:
            options['policy'] = policy

        # reconfigure if any of the parameters is specified
        if options:
            existing = None
            try:
                existing = restclient.get(restapi, url).json()
            except restclient.NotFoundError:
                _LOGGER.debug('App monitor not found: %s', name)

            if existing is None:
                _check_configure_usage(count)

                _LOGGER.debug('Creating app monitor: %s', name)
                restclient.post(restapi, url, payload=options)

            else:
                existing.update(options)
                _LOGGER.debug('Updating app monitor: %s', name)
                restclient.put(restapi, url, payload=existing)

        _LOGGER.debug('Retrieving app monitor: %s', name)
        monitor_entry = restclient.get(restapi, url)
        cli.out(formatter(monitor_entry.json()))

    @monitor_group.command(name='list')
    @click.option('--match', help='Monitor name pattern match')
    @_ON_EXCEPTIONS
    def _list(match):
        """List configured app monitors"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH
        if match:
            query = {'match': match}
            url += '?' + urllib_parse.urlencode(query)

        response = restclient.get(restapi, url)
        cli.out(formatter(response.json()))

    @monitor_group.command()
    @click.argument('name', nargs=1, required=True)
    @_ON_EXCEPTIONS
    def delete(name):
        """Delete app monitor"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    del delete
    del _list
    del configure

    return monitor_group
