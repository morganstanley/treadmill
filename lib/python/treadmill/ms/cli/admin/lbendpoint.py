"""Admin CLI to make low level changes to LB Endpoint
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import admin
from treadmill import cli
from treadmill import context

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbendpoint as tlbendpoint
from treadmill.ms import lbcontrol
from treadmill.ms.api import lbendpoint as albendpoint

_LOGGER = logging.getLogger(__name__)


def _enable_logging():
    """Enable info level logging."""
    if not _LOGGER.isEnabledFor(logging.INFO):
        _LOGGER.setLevel(logging.INFO)


def _get_disabled_members(lbc, virtual):
    """Get disabled pool members."""
    pool_status = lbc.virtual_pool_status(virtual, virtual)
    non_active_services = []
    for svc in pool_status.service_healths:
        if svc.name == '8.8.8.8.dummy.42':
            continue

        if (svc.device_config_state !=
                lbcontrol.DeviceConfigState.enabled):
            _LOGGER.info('%s: %s', svc.name, svc.device_config_state)
            non_active_services.append(svc.name)
        else:
            _LOGGER.info('%s: ok', svc.name)

    return non_active_services


def _svcname_2_svc(svc_name):
    """Convert service name to service."""
    hostname, _proto, port = svc_name.rsplit('.', 2)
    return {
        'service_name': svc_name,
        'hostname': hostname,
        'port': port,
    }


def _fix(lbc, virtual_name, services):
    """Fix pool services by activating them and/or pushing the device."""
    _LOGGER.info('Fixing: %s: %r', virtual_name, services)
    try:
        pool_name = virtual_name
        lbc.modify_pool_member_state(
            virtual_name,
            pool_name,
            services=[_svcname_2_svc(name) for name in services],
            transition_type='ACTIVATE',
        )
    except lbcontrol.SOAPError:
        lbc.push_virtual(virtual_name)


def _lbendpoint(name):
    """Get lbendpoint by name from LDAP."""
    admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
    lbendpoints = admin_app_group.list({
        '_id': name,
        'group-type': 'lbendpoint',
    })
    _LOGGER.debug('lbendpoints: %r', lbendpoints)

    if not lbendpoints:
        return None

    return tlbendpoint.group2lbendpoint(lbendpoints[0])


def _check_lbendpoint(lbc, lbep, cells, fix):
    """Check state of the lbendpoint."""
    if not cells:
        cells = lbep['cells']

    virtuals = tlbendpoint.filter_cell_virtuals(lbep['virtuals'], cells)

    for virtual in virtuals:
        pool = lbc.get_pool(virtual)
        if not pool:
            _LOGGER.info('Pool is empty: %s', virtual)
            continue

        members = [member.service.name for member in pool.members
                   if member.service.name != '8.8.8.8.dummy.42']
        if not members:
            _LOGGER.info('No members: %s', virtual)
            continue

        non_active_services = _get_disabled_members(lbc, virtual)
        if non_active_services:
            if fix:
                _fix(lbc, virtual, non_active_services)
                not_fixed = _get_disabled_members(lbc, virtual)
                if not_fixed:
                    _LOGGER.error('%s: %r', virtual, not_fixed)


def init():
    """Initiliaze LB endpoint"""
    formatter = cli.make_formatter('ms-lbendpoint')

    @click.group()
    def lbendpoint():
        """Manage LB endpoint"""
        pass

    @lbendpoint.command()
    @click.argument('name')
    @click.option('--vips', help='VIPs', type=cli.LIST)
    @click.option('--virtuals', help='Virtuals', type=cli.LIST)
    @click.option('--endpoint', help='Endpoint name')
    @click.option('--pattern', help='App pattern')
    @click.option('--port', help='LB Port')
    @click.option('--environment', help='Environment of the LB')
    @click.option('--cells', help='Cell app pattern could be in; comma '
                  'separated list of cells', type=cli.LIST)
    @cli.admin.ON_EXCEPTIONS
    def configure(name, vips, virtuals, endpoint, pattern, port, environment,
                  cells):
        """Configure lbendpoint"""
        lbep = _lbendpoint(name)
        _LOGGER.debug('lbep: %r', lbep)

        existed = True
        if not lbep:
            lbep = {'_id': name}
            existed = False

        if (not vips and
                not virtuals and
                not endpoint and
                not cells and
                not environment):
            return cli.out(formatter(lbep))

        if vips:
            lbep['vips'] = vips
        if virtuals:
            lbep['virtuals'] = virtuals
        if cells:
            lbep['cells'] = cells
        if endpoint:
            lbep['endpoint'] = endpoint
        if port:
            lbep['port'] = port
        if pattern:
            lbep['pattern'] = pattern
        if environment:
            lbep['environment'] = environment

        _LOGGER.debug('lbep: %r', lbep)

        app_group = tlbendpoint.lbendpoint2group(lbep)
        _LOGGER.debug('app_group: %r', app_group)

        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        if existed:
            admin_app_group.replace(name, app_group)
        else:
            admin_app_group.create(name, app_group)

        cli.out(formatter(lbep))

    @lbendpoint.command()
    @click.argument('name')
    @click.option('--cells', help='Comma (,) separated list of cells',
                  type=cli.LIST, required=True)
    @click.option('--lbenv', help='LB Environment', default='prod')
    def push(name, cells, lbenv):
        """Push lbendpoint virtual."""

        lbep = _lbendpoint(name)
        virtuals = tlbendpoint.filter_cell_virtuals(lbep['virtuals'], cells)
        lbc = lbcontrol.LBControl2(lbenv)

        for lbvirtual in virtuals:
            click.echo('Push: {}'.format(lbvirtual))
            lbc.push_virtual(lbvirtual)

    @lbendpoint.command()
    @click.argument('name')
    @click.option('--cells', help='Comma (,) separated list of cells',
                  type=cli.LIST, required=True)
    @click.option('--fix', is_flag=True, default=False,
                  help='Fix non-active pool members.')
    @click.option('--lbenv', help='LB Environment', default='prod')
    def check(name, cells, fix, lbenv):
        """Check lbendpoint status."""
        _enable_logging()
        lbc = lbcontrol.LBControl2(lbenv)
        lbep = _lbendpoint(name)
        _check_lbendpoint(lbc, lbep, cells, fix)

    @lbendpoint.command(name='check-all')
    @click.option('--fix', is_flag=True, default=False,
                  help='Fix non-active pool members.')
    @click.option('--lbenv', help='LB Environment', default='prod')
    def check_all(fix, lbenv):
        """Check lbendpoint status."""
        _enable_logging()
        lbc = lbcontrol.LBControl2(lbenv)
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        app_groups = admin_app_group.list({
            'group-type': 'lbendpoint',
        })
        lbendpoints = [tlbendpoint.group2lbendpoint(app_group)
                       for app_group in app_groups]
        for lbep in lbendpoints:
            _LOGGER.info('Checking lbendpoint: %s', lbep['_id'])
            _check_lbendpoint(lbc, lbep, None, fix)

    @lbendpoint.command()
    @click.argument('name')
    @click.option('--lbenv', help='LB Environment', default='prod')
    @cli.admin.ON_EXCEPTIONS
    def delete(name, lbenv):
        """Delete an lbendpoint, virtual, and pool"""
        _lbendpoint(name)
        api = albendpoint.API()
        api.delete(name, lbenv)

    @lbendpoint.command(name='list')
    def _list():
        """List all LB endpoints"""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        app_groups = admin_app_group.list({
            'group-type': 'lbendpoint',
        })
        _LOGGER.debug('app_groups: %r', app_groups)

        lbendpoints = [tlbendpoint.group2lbendpoint(app_group)
                       for app_group in app_groups]
        _LOGGER.debug('lbendpoints: %r', lbendpoints)

        cli.out(formatter(lbendpoints))

    del configure
    del delete
    del push
    del check
    del check_all
    del _list

    return lbendpoint
