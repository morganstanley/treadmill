"""Treadmill App DNS CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)

_REST_PATH = '/app-dns/'


def init():
    """Configures App DNS"""
    formatter = cli.make_formatter('app-dns')

    @click.group(name='app-dns')
    def appdns():
        """Manage Treadmill App DNS configuration.
        """

    @appdns.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--cell', help='List of cells',
                  type=cli.LIST)
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoints', help='Endpoints to be included in SRV rec',
                  type=cli.LIST)
    @click.option('--alias', help='App DNS alias')
    @click.option('--scope', help='DNS scope')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(name, cell, pattern, endpoints, alias, scope):
        """Create, modify or get Treadmill App DNS entry"""
        restapi = context.GLOBAL.admin_api()
        url = _REST_PATH + name
        data = {}

        if cell:
            data['cells'] = cell
        if pattern is not None:
            data['pattern'] = pattern
        if endpoints is not None:
            data['endpoints'] = endpoints
        if alias is not None:
            data['alias'] = alias
        if scope is not None:
            data['scope'] = scope

        if data:
            try:
                _LOGGER.debug('Trying to create app-dns entry %s', name)
                restclient.post(restapi, url, data)
            except restclient.AlreadyExistsError:
                _LOGGER.debug('Updating app-dns entry %s', name)
                restclient.put(restapi, url, data)

        _LOGGER.debug('Retrieving App DNS entry %s', name)
        app_dns_entry = restclient.get(restapi, url).json()

        cli.out(formatter(app_dns_entry))

    @appdns.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--add', help='Cells to to add.', type=cli.LIST)
    @click.option('--remove', help='Cells to to remove.', type=cli.LIST)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def cells(add, remove, name):
        """Add or remove cells from the app-dns."""
        url = _REST_PATH + name
        restapi = context.GLOBAL.admin_api()
        existing = restclient.get(restapi, url).json()

        cells = set(existing['cells'])

        if add:
            cells.update(add)
        if remove:
            cells = cells - set(remove)

        if '_id' in existing:
            del existing['_id']
        existing['cells'] = list(cells)
        restclient.put(restapi, url, existing)

    @appdns.command(name='list')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list():
        """List out App Group entries"""
        restapi = context.GLOBAL.admin_api()
        response = restclient.get(restapi, _REST_PATH)
        cli.out(formatter(response.json()))

    @appdns.command()
    @click.argument('name', nargs=1, required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def delete(name):
        """Delete Treadmill App Group entry"""
        restapi = context.GLOBAL.admin_api()
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    del delete
    del cells
    del _list
    del configure

    return appdns
