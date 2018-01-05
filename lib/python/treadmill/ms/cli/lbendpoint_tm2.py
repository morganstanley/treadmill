"""Treadmill lbendpoint-tm2 CLI.
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
from treadmill.formatter import tablefmt


_LOGGER = logging.getLogger(__name__)

_ON_EXCEPTIONS = cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)

_REST_PATH = '/lbendpoint-tm2/'


class LBEndpointTM2PrettyFormatter(object):
    """Pretty table lbendpoint-tm2 formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', '_id', None),
            ('vip', 'vip', None),
            ('port', 'port', None),
            ('location', None, None),
            ('cells', None, None),
            ('pattern', None, None),
            ('endpoint', None, None),
        ]

        format_item = tablefmt.make_dict_to_table(schema)
        format_list = tablefmt.make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)


def init():
    """init"""
    formatter = cli.make_formatter('ms-lbendpoint-tm2')
    ctx = {}

    @click.group()
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    def lbendpoint_tm2(api):
        """Manage lbendpoint-tm2."""
        ctx['api'] = api

    @lbendpoint_tm2.command()
    @click.argument('name')
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoint', help='App endpoint')
    @click.option('--cells', help='Comma separated list of cells',
                  type=cli.LIST)
    @_ON_EXCEPTIONS
    def configure(name, pattern, endpoint, cells):
        """Configure (get/update) TM2 lbendpoint."""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name

        _LOGGER.debug('Retrieving TM2 lbendpoint: %s', name)
        response = restclient.get(restapi, url)
        lbendpoint = response.json()

        data = {}
        if pattern:
            data['pattern'] = pattern
        if endpoint:
            data['endpoint'] = endpoint
        if cells is not None:
            data['cells'] = [cell for cell in cells if cell]

        if data:
            _LOGGER.debug('Updating TM2 lbendpoint: %s', name)
            response = restclient.put(restapi, url, payload=data)
            lbendpoint = response.json()

        cli.out(formatter(lbendpoint))

    @lbendpoint_tm2.command()
    @click.argument('name')
    @_ON_EXCEPTIONS
    def delete(name):
        """Delete TM2 lbendpoint and virtual/pool."""
        if not click.confirm('Delete lbendpoint and virtual/pool?'):
            return
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name
        restclient.delete(restapi, url)

    @lbendpoint_tm2.command(name='list')
    @_ON_EXCEPTIONS
    def _list():
        """List TM2 lbendpoints."""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        response = restclient.get(restapi, _REST_PATH)
        cli.out(formatter(response.json()))

    del configure
    del delete
    del _list

    return lbendpoint_tm2
