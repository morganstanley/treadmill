"""Treadmill Identity Group CLI

Create, delete and manage identity groups.
"""


import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient


_LOGGER = logging.getLogger(__name__)

_EXCEPTIONS = []
_EXCEPTIONS.extend(cli.REST_EXCEPTIONS)

_ON_EXCEPTIONS = cli.handle_exceptions(_EXCEPTIONS)

_REST_PATH = '/identity-group/'


def init():  # pylint: disable=R0912
    """Configures identity group."""
    formatter = cli.make_formatter(cli.IdentityGroupPrettyFormatter)
    ctx = {}

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    def monitor_group(api):
        """Manage identity group configuration"""
        ctx['api'] = api

    @monitor_group.command()
    @click.option('-n', '--count', type=int, help='Identity count')
    @click.argument('name')
    @_ON_EXCEPTIONS
    def configure(count, name):
        """Configure application monitor"""
        restapi = context.GLOBAL.cell_api(ctx['api'])
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
        restapi = context.GLOBAL.cell_api(ctx['api'])
        response = restclient.get(restapi, '/identity-group/')
        cli.out(formatter(response.json()))

    @monitor_group.command()
    @click.argument('name', nargs=1, required=True)
    @_ON_EXCEPTIONS
    def delete(name):
        """Delete identity group"""
        restapi = context.GLOBAL.cell_api(ctx['api'])
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    del delete
    del _list
    del configure

    return monitor_group
