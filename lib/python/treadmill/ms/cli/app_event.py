"""Treadmill App Event CLI.
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
from treadmill.formatter import tablefmt

_LOGGER = logging.getLogger(__name__)

_REST_PATH = '/app-event/'


class AppEventPrettyFormatter(object):
    """Pretty table App Groups formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', '_id', None),
                  ('cells', None, None),
                  ('pattern', None, None),
                  ('exit', None, None),
                  ('pending', None, None)]

        format_item = tablefmt.make_dict_to_table(schema)
        format_list = tablefmt.make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)


def init():
    """Configures App event"""
    formatter = cli.make_formatter('ms-app-event')
    ctx = {}

    @click.group(name='app-event')
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    def appevent(api):
        """Manage Treadmill App event configuration"""
        ctx['api'] = api

    # pylint: disable=W0622
    @appevent.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--cell', help='Cell app pattern could be in comma '
                  'separated list of cells', type=cli.LIST)
    @click.option('--pattern', help='App pattern')
    @click.option('--exit', help='Exit event type could be in comma '
                  'separated list of exit type',
                  type=cli.Enums(['non-zero', 'oom', 'aborted']))
    @click.option('--pending', type=int, help='pending seconds')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(name, cell, pattern, exit, pending):
        """Create, modify or get Treadmill App Event entry"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name
        data = {}

        if cell:
            data['cells'] = cell
        if pattern is not None:
            data['pattern'] = pattern
        if pending is not None:
            data['pending'] = pending
        if exit is not None:
            data['exit'] = exit

        if data:
            try:
                _LOGGER.debug('Trying to create app-event entry %s', name)
                restclient.post(restapi, url, data)
            except restclient.AlreadyExistsError:
                _LOGGER.debug('Updating app-event entry %s', name)
                restclient.put(restapi, url, data)

        _LOGGER.debug('Retrieving App Event entry %s', name)
        app_event_entry = restclient.get(restapi, url).json()

        cli.out(formatter(app_event_entry))

    @appevent.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--add', help='Cells to to add.', type=cli.LIST)
    @click.option('--remove', help='Cells to to remove.', type=cli.LIST)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def cells(add, remove, name):
        """Add or remove cells from the app-event."""
        url = _REST_PATH + name
        restapi = context.GLOBAL.admin_api(ctx['api'])
        existing = restclient.get(restapi, url).json()

        cells = set(existing['cells'])

        if add:
            cells.update(add)
        if remove:
            cells = cells - set(remove)

        if '_id' in existing:
            del existing['_id']
        existing['cells'] = list(cells)

        # if value is None, we do not submit
        if existing['pending'] is None:
            del existing['pending']
        if existing['exit'] is None:
            del existing['exit']

        restclient.put(restapi, url, existing)

    @appevent.command(name='list')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list():
        """List out App Group entries"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        response = restclient.get(restapi, _REST_PATH)
        cli.out(formatter(response.json()))

    @appevent.command()
    @click.argument('name', nargs=1, required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def delete(name):
        """Delete Treadmill App Group entry"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    del delete
    del cells
    del _list
    del configure

    return appevent
