"""Treadmill Identity Group CLI

Create, delete and manage identity groups.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient


_LOGGER = logging.getLogger(__name__)

_EXCEPTIONS = []
_EXCEPTIONS.extend(restclient.CLI_REST_EXCEPTIONS)

_ON_EXCEPTIONS = cli.handle_exceptions(_EXCEPTIONS)

_REST_PATH = '/identity-group/'


def init():  # pylint: disable=R0912
    """Configures identity group."""
    formatter = cli.make_formatter('identity-group')

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
        """Manage identity group configuration.
        """

    @monitor_group.command()
    @click.option('-n', '--count', type=int, help='Identity count')
    @click.argument('name')
    @_ON_EXCEPTIONS
    def configure(count, name):
        """Configure application monitor"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + name

        if count is not None:
            data = {'count': count}
            try:
                _LOGGER.debug('Creating identity group: %s', name)
                restclient.post(restapi, url, payload=data)
            except restclient.AlreadyExistsError:
                _LOGGER.debug('Updating identity group: %s', name)
                restclient.put(restapi, url, payload=data)

        _LOGGER.debug('Retrieving identity group: %s', name)
        monitor_entry = restclient.get(restapi, url)
        cli.out(formatter(monitor_entry.json()))

    @monitor_group.command(name='list')
    @_ON_EXCEPTIONS
    def _list():
        """List configured identity groups"""
        restapi = context.GLOBAL.cell_api()
        response = restclient.get(restapi, '/identity-group/')
        cli.out(formatter(response.json()))

    @monitor_group.command()
    @click.argument('name', nargs=1, required=True)
    @_ON_EXCEPTIONS
    def delete(name):
        """Delete identity group"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    del delete
    del _list
    del configure

    return monitor_group
