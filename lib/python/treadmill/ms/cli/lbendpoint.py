"""Treadmill lbendpoint CLI

Create, delete and manage your lbendpoints. Under the hood, these use
app-groups.
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

_ON_EXCEPTIONS = cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)

_REST_PATH = '/lbendpoint/'

_REQUEST_TIMEOUT = 600  # 5 minutes, as creating 4+ VIPs takes time


class LBEndpointPrettyFormatter(object):
    """Pretty table LBEndpoint formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [
            ('name', '_id', None),
            ('cells', None, None),
            ('pattern', None, None),
            ('endpoint', None, None),
            ('environment', None, None),
            ('port', None, None),
        ]

        format_item = tablefmt.make_dict_to_table(schema)
        format_list = tablefmt.make_list_to_table(schema)

        if isinstance(item, list):
            return format_list(item)

        schema.append(('vips', None, '\n'.join))
        if 'options' in item:
            options_tbl = tablefmt.make_dict_to_table([
                ('conn-timeout', 'conn_timeout', None),
                ('lb-method', 'lb_method', None),
                ('min-active', 'min_active', None),
                ('persist-timeout', 'persist_timeout', None),
                ('persist-type', 'persist_type', None),
                ('svc-down-action', 'svc_down_action', None),
            ])
            schema.append(('options', None, options_tbl))

        return format_item(item)


def init():  # pylint: disable=R0912
    """Configures LB endpoint"""
    formatter = cli.make_formatter('ms-lbendpoint')
    ctx = {}

    @click.group()
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    def lbendpoint_group(api):
        """Manage Treadmill LB endpoint configuration"""
        ctx['api'] = api

    @lbendpoint_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--cell', help='Cell app pattern could be in; comma '
                  'separated list of cells', type=cli.LIST)
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoint', help='App endpoint')
    @click.option('--port', help='Desired port; only admin can supply',
                  type=int)
    @_ON_EXCEPTIONS
    def configure(name, cell, pattern, endpoint, port):
        """Create, modify or get an LB endpoint entry"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name

        data = dict()
        if cell:
            data['cells'] = cell
        if pattern is not None:
            data['pattern'] = pattern
        if endpoint is not None:
            data['endpoint'] = endpoint
        if port is not None:
            data['port'] = port

        try:
            _LOGGER.debug('Retrieving LB endpoint entry %s', name)
            response = restclient.get(restapi, url)
            lbendpoint = response.json()
        except restclient.NotFoundError:
            lbendpoint = None
            if len(data) <= 1:
                raise

        if len(data) > 1:
            if lbendpoint:
                _LOGGER.debug('Updating LB Endpoint entry %s', name)
                response = restclient.put(restapi, url, payload=data,
                                          timeout=_REQUEST_TIMEOUT)
            else:
                _LOGGER.debug('Trying to create LB Endpoint entry %s', name)
                click.echo('WARNING: creating a new LB can take up to '
                           '5 minutes', err=True)
                response = restclient.post(restapi, url, payload=data,
                                           timeout=_REQUEST_TIMEOUT)
            lbendpoint = response.json()

        cli.out(formatter(lbendpoint))

    @lbendpoint_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--add', help='Cells to to add.', type=cli.LIST)
    @click.option('--remove', help='Cells to to remove.', type=cli.LIST)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def cells(add, remove, name):
        """Add or remove cells from the lbendpoint"""
        url = _REST_PATH + name
        restapi = context.GLOBAL.admin_api(ctx['api'])
        existing = restclient.get(restapi, url).json()

        cells = set(existing['cells'])
        if add:
            cells.update(add)
        if remove:
            cells = cells - set(remove)
        existing['cells'] = list(cells)

        if '_id' in existing:
            del existing['_id']
        del existing['port']

        _LOGGER.debug('existing: %r', existing)
        click.echo('WARNING: creating a new LB can take up to 5 minutes',
                   err=True)
        response = restclient.put(restapi, url, payload=existing,
                                  timeout=_REQUEST_TIMEOUT)

        cli.out(formatter(response.json()))

    @lbendpoint_group.command(name='list')
    @_ON_EXCEPTIONS
    def _list():
        """List out LB endpoint entries"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        response = restclient.get(restapi, _REST_PATH)
        sorted_lbs = sorted(
            response.json(), key=lambda x: x['_id']
        )
        cli.out(formatter(sorted_lbs))

    @lbendpoint_group.command()
    @click.argument('name', nargs=1, required=True)
    @_ON_EXCEPTIONS
    def delete(name):
        """Delete an LB endpoint entry"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name
        restclient.delete(restapi, url, timeout=_REQUEST_TIMEOUT)

    @lbendpoint_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('-conn-to', '--conn-timeout', help='Connection idle timeout',
                  type=int)
    @click.option('--lb-method', help='Load balancing method',
                  type=click.Choice(['round_robin', 'member_ratio',
                                     'member_least_conn', 'member_observed',
                                     'member_predictive', 'ratio',
                                     'least_conn', 'fastest', 'observed',
                                     'predictive', 'dynamic_ratio',
                                     'fastest_app_resp', 'least_sessions',
                                     'member_dynamic_ratio', 'l3_addr']))
    @click.option('--min-active', help='Number of active services before'
                  ' reporting outage in the pool', type=int)
    @click.option('-pers', '--persist-type', help='Persist type',
                  type=click.Choice(['none', 'cookie', 'ssl', 'source_addr',
                                     'dest_addr']))
    @click.option('-pers-to', '--persist-timeout', help='Persist timeout',
                  type=int)
    @click.option('--svc-down-action', help='Service down action',
                  type=click.Choice(['none', 'reset', 'drop', 'reselect']))
    @_ON_EXCEPTIONS
    def options(name, conn_timeout, lb_method, min_active, persist_type,
                persist_timeout, svc_down_action):
        """Get or update the options of an existing virtual"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + name

        data = dict(options={})

        if conn_timeout is not None:
            data['options']['conn_timeout'] = conn_timeout
        if lb_method is not None:
            data['options']['lb_method'] = lb_method
        if min_active is not None:
            data['options']['min_active'] = min_active
        if persist_type is not None:
            data['options']['persist_type'] = persist_type
        if persist_timeout is not None:
            data['options']['persist_timeout'] = persist_timeout
        if svc_down_action is not None:
            data['options']['svc_down_action'] = svc_down_action

        if data['options']:
            _LOGGER.debug('Updating options of the LB Endpoint entry %s', name)
            restclient.put(
                restapi, url, payload=data, timeout=_REQUEST_TIMEOUT
            )

        lbendpoint_entry = restclient.get(restapi, url)

        lbendpoint = lbendpoint_entry.json()
        _LOGGER.debug('Got %s', lbendpoint)
        cli.out(formatter(lbendpoint))

    del delete
    del cells
    del _list
    del configure
    del options

    return lbendpoint_group
