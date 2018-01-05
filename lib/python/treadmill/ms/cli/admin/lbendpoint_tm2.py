"""Treadmill lbendpoint-tm2 admin CLI.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import restclient

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbendpoint
from treadmill.ms.api import lbendpoint_tm2 as lbendpoint_tm2_api


_TM2_API = 'http://treadmill-rest.ms.com:4001'
_TM2_LBENDPOINT_URL = '/api/cloud/treadmill/lbendpoint'

_LOCATIONS = {
    'hk': 'as.hk',
    'tk': 'as.tk',
    'ln': 'eu.ln',
    'ny': 'na.ny',
    'vi': 'na.vi'
}


def _get_json(api, url):
    return restclient.get(api, url, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }).json()


def _update_cell_vips(vip, location):
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

    location_cells = admin_cell.list({'location': location})
    for cell in location_cells:
        try:
            cell_vips = cell['data']['lbvirtual']['vips']
        except KeyError:
            cell_vips = None

        if cell_vips is not None and vip not in cell_vips:
            cli.out('Adding %s to %s lbvirtual vips', vip, cell['_id'])
            cell_vips.append(vip)
            admin_cell.replace(cell['_id'], cell)


def init():
    """init"""
    formatter = cli.make_formatter('ms-lbendpoint-tm2')

    @click.group()
    def lbendpoint_tm2():
        """Manage lbendpoint-tm2."""
        pass

    @lbendpoint_tm2.command(name='import')
    @click.argument('names', nargs=-1, required=False)
    @click.option('--replace/--no-replace',
                  help='Replace if already exists',
                  is_flag=True, default=False)
    @cli.admin.ON_EXCEPTIONS
    def _import(names, replace):
        """Import TM2 lbendpoints."""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)

        if not names:
            if not click.confirm('Import all TM2 lbendpoints to TM3?'):
                return
            names = _get_json(_TM2_API, _TM2_LBENDPOINT_URL)

        for name in names:
            cli.out('Importing %s', name)
            resp = _get_json(
                _TM2_API, '{}/{}'.format(_TM2_LBENDPOINT_URL, name)
            )

            if not resp:
                cli.echo_yellow('%s not found, skipping', name)
                continue

            if '_error' in resp:
                cli.echo_red('Error importing %s: %s, skipping',
                             name, resp['_error'])
                continue

            if name != resp['_id']:
                cli.echo_yellow('Invalid id: %s != %s, skipping',
                                name, resp['_id'])
                continue

            lbe = {
                '_id': resp['_id'],
                'vip': resp['vip'],
                'port': resp['port'],
                'virtual': '{}.{}'.format(resp['vip'], resp['port']),
                'location': _LOCATIONS[resp['location']],
                'pattern': resp['pattern'],
                'endpoint': resp['endpoint']
            }
            group = lbendpoint.lbendpoint2group(lbe, 'lbendpoint-tm2')

            _update_cell_vips(lbe['vip'], lbe['location'])

            try:
                admin_app_group.create(name, group)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                if replace:
                    admin_app_group.replace(name, group)
                else:
                    cli.out('%s already exists, skipping', name)
                    continue

            lbe = lbendpoint.group2lbendpoint(
                admin_app_group.get(name, 'lbendpoint-tm2')
            )
            cli.out(formatter(lbe))

    @lbendpoint_tm2.command()
    @click.argument('name')
    @click.option('--vip', help='VIP')
    @click.option('--port', help='Port', type=int)
    @click.option('--location', help='Location')
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoint', help='App endpoint')
    @click.option('--cells', help='Comma separated list of cells',
                  type=cli.LIST)
    @cli.admin.ON_EXCEPTIONS
    def configure(name, vip, port, location, pattern, endpoint, cells):
        """Configure (get/create/update) TM2 lbendpoint."""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)

        try:
            lbe = lbendpoint.group2lbendpoint(
                admin_app_group.get(name, 'lbendpoint-tm2')
            )
        except ldap_exceptions.LDAPNoSuchObjectResult:
            lbe = {}

        data = {}
        if vip:
            data['vip'] = vip
        if port:
            data['port'] = port
        if location:
            data['location'] = location
        if pattern:
            data['pattern'] = pattern
        if endpoint:
            data['endpoint'] = endpoint
        if cells is not None:
            data['cells'] = [cell for cell in cells if cell]

        if not lbe and not data:
            cli.bad_exit('TM2 lbendpoint does not exist: %s', name)

        if not lbe and not all((vip, port, location)):
            cli.bad_exit('vip, port and location are required')

        if data:
            lbe.update(data)
            lbe['_id'] = name
            lbe['virtual'] = '{}.{}'.format(lbe['vip'], lbe['port'])

            _update_cell_vips(lbe['vip'], lbe['location'])

            group = lbendpoint.lbendpoint2group(lbe, 'lbendpoint-tm2')
            try:
                admin_app_group.create(name, group)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_app_group.replace(name, group)

            lbe = lbendpoint.group2lbendpoint(
                admin_app_group.get(name, 'lbendpoint-tm2')
            )

        cli.out(formatter(lbe))

    @lbendpoint_tm2.command()
    @click.argument('name')
    @cli.admin.ON_EXCEPTIONS
    def delete(name):
        """Delete TM2 lbendpoint and virtual/pool."""
        if not click.confirm('Delete lbendpoint and virtual/pool?'):
            return
        api = lbendpoint_tm2_api.API()
        api.delete(name)

    @lbendpoint_tm2.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List TM2 lbendpoints."""
        api = lbendpoint_tm2_api.API()
        cli.out(formatter(api.list()))

    del _import
    del configure
    del delete
    del _list

    return lbendpoint_tm2
