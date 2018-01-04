"""Some simple common helper functions for LB endpoint.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import copy
import logging
import re
import random

import six

from treadmill import admin
from treadmill import context
from treadmill import utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol

_LOGGER = logging.getLogger(__name__)

DEFAULT_VIP0_SEARCH_STR = 'treadmill-%-{0}-v3-%.ms.com.0'
DEFAULT_VIRTUAL_SEARCH_STR = '{0}%'.format(DEFAULT_VIP0_SEARCH_STR)
DEFAULT_POOL_SEARCH_STR = '{0}.%'.format(DEFAULT_VIP0_SEARCH_STR)

ASSIGN_PORT_START = 5000
MAX_PORT_VALUE = 65535

_TREADMILL_EONID = 43626
DUMMY_SVC = '8.8.8.8.dummy.42'

VIRTUAL_NAME_REGEX = r'treadmill-(\w{2})-(dev|prod)-v3-(\d)+\.ms\.com\.0'
VIP0_NAME_REGEX = r'{0}$'.format(VIRTUAL_NAME_REGEX)
POOL_NAME_REGEX = r'{0}.(\d)+'.format(VIRTUAL_NAME_REGEX)

_LBENDPOINT_DATA_ATTRS = {
    'lbendpoint': {
        'port': int,
        'virtuals': lambda virtuals: sorted(virtuals.split(',')),
        'vips': lambda vips: sorted(vips.split(',')),
        'environment': None,
    },
    'lbendpoint-tm2': {
        'port': int,
        'virtual': None,
        'vip': None,
        'location': None,
    },
}


class NoVirtualsError(Exception):
    """Simple exception when no virtuals can be found"""
    pass


class PortInUseError(Exception):
    """Simple exception when port is in use"""
    pass


class NoAvailablePortError(Exception):
    """Simple exception when no available ports on any virtuals"""
    pass


class PoolAlreadyExistsError(Exception):
    """Simple exception when a pool already exists"""
    pass


def delete_lbendpoint_virtual(lbc, virtual):
    """Delete/remove existing lbendpoint virtual safely"""
    try:
        lbc.delete_virtual(virtual)
    except lbcontrol.SOAPError:
        _LOGGER.exception('Could not delete pool %s', virtual)

    try:
        lbc.delete_pool(virtual)
    except lbcontrol.SOAPError:
        _LOGGER.exception('Could not delete pool %s', virtual)


def create_pool(lbc, poolname):
    """Create a pool with a dummy service"""
    virt_pool = lbc.get_pool(poolname, raw=True)
    if virt_pool:
        raise PoolAlreadyExistsError('%s already exists' % poolname)

    monitor = lbc.get_monitor('tcp-half-open')
    _LOGGER.debug('monitor: %r', monitor)

    service = lbc.get_service(DUMMY_SVC)
    _LOGGER.debug('service: %r', service)

    pool = dict(
        monitors=[monitor],
        comments=[dict(_comment='New lbendpoint pool %s' % poolname)],
        members=[dict(service=service)]
    )

    return lbc.create_pool(poolname, pool)


def create_lbendpoint_virtual(lbc, vip0_name, port, prodstatus):
    """Create a new virtual for a user's lbendpoint"""
    # First, get the highest level virtual
    poolname = '{0}.{1}'.format(vip0_name, port)
    create_pool(lbc, poolname)

    virt_pool = lbc.get_pool(poolname, raw=True)
    _LOGGER.debug('virt_pool: %r', virt_pool)
    if not virt_pool:
        raise NoVirtualsError('Could not create virtual pool %s' % poolname)

    vip0 = lbc.get_virtual(vip0_name, raw=True)

    # Enums are scriptable-objects despite E1136
    # pylint: disable=E1136
    _prodstatus = lbcontrol.ProdStatus[prodstatus].value

    # W0212: Access to a protected member %s of a client class
    # pylint: disable=W0212
    new_vip = {
        '_ipAddress': vip0._ipAddress,
        '_snataddress': vip0._snataddress,
        '_port': int(port),
        '_protocol': vip0._protocol,
        '_eonid': _TREADMILL_EONID,
        '_owner': vip0._owner,
        '_hold': 'false',
        '_prodstatus': _prodstatus,
        'cluster': vip0.cluster,
        'pool': virt_pool,
        'template': vip0.template,
        'comments': [dict(_comment='New lbendpoint virtual %s' % poolname)],
    }

    res = lbc.create_virtual(poolname, new_vip)
    _LOGGER.debug('res: %r', res)


def update_lbendpoint_virtual(lbc, vip_name, options):
    """Update a virtual"""
    updates = {}
    # map the attributes to the lbcontrol api expeted form
    if 'conn_timeout' in options:
        updates['_conntimeout'] = options['conn_timeout']
    if 'persist_type' in options:
        updates['_persisttype'] = options['persist_type']
    if 'persist_timeout' in options:
        updates['_persisttimeout'] = options['persist_timeout']

    if updates:
        _LOGGER.debug('Updating %r with %r', vip_name, updates)
        res = lbc.update_virtual(vip_name, updates, raw=True)
        _LOGGER.debug('res: %r', res)

    updates = {k: v
               for k, v in options.items()
               if k in {'lb_method', 'min_active', 'svc_down_action'}}

    if updates:
        _LOGGER.debug('Updating pool %r with %r', vip_name, updates)
        res = lbc.update_pool_parameters(vip_name, vip_name, **updates)
        _LOGGER.debug('res: %r', res)


def get_lbendpoint_virtual(lbc, vip_name):
    """Get a virtual"""
    virt = lbc.get_virtual(vip_name)
    if not virt:
        return None

    # Virtuals should have pool assicoated with them and it should be returned.
    pool = getattr(virt, 'pool', None)
    if not pool:
        pool = lbc.get_pool(vip_name)

    options = {key: getattr(virt, key, None) for key in {'conn_timeout',
                                                         'persist_timeout',
                                                         'persist_type'}}

    for key in {'lb_method', 'min_active', 'svc_down_action'}:
        options[key] = getattr(pool, key, None)

    return {
        'options': options,
        'prodstatus': getattr(virt, 'prodstatus', None),
    }


def filter_cell_virtuals(virtuals, cells):
    """Utility method to retrieve virtuals for the given cells"""
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

    filtered_virtuals = set()
    for cell_name in cells:
        cell = admin_cell.get(cell_name)
        location = cell['location']
        _region, campus = location.split('.')
        _LOGGER.debug('cell_name: %s, campus: %s', cell_name, campus)

        for virtual in virtuals:
            if campus in virtual:
                filtered_virtuals.add(virtual)

    return list(filtered_virtuals)


def push_cell_virtuals(lbc, virtuals, cells):
    """Push virtuals only if they are in the lbendpoints cells location"""
    filtered_virtuals = filter_cell_virtuals(virtuals, cells)

    for virtual in filtered_virtuals:
        _LOGGER.info('Pushing %s', virtual)
        lbc.push_virtual(virtual)


def in_use_lbendpoint_ports(environment, vips):
    """Get the "in use" LB endpoints from a the app-groups"""
    admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
    app_groups = admin_app_group.list({
        'environment': environment,
        'group-type': 'lbendpoint',
    })
    _LOGGER.debug('app_groups: %r', app_groups)

    vips_to_used_ports = collections.defaultdict(list)
    for app_group in app_groups:
        lbe_entry = group2lbendpoint(app_group)

        port = lbe_entry.get('port')
        if not port:
            continue

        for vip in vips:
            vips_to_used_ports[vip].append(int(port))

    return vips_to_used_ports


def get_vips(lbc, environment, search=None):
    """Get all the high level VIPs"""
    if not search:
        search = DEFAULT_VIRTUAL_SEARCH_STR.format(environment)

    virtuals = lbc.list_virtuals(search)
    _LOGGER.debug('virtuals: %r', virtuals)

    if not virtuals:
        raise NoVirtualsError(
            'No virtuals defined in %s, using search %s' %
            (environment, search))

    virtual_names = [virt.name for virt in virtuals]
    random.shuffle(virtual_names)

    high_level_vips = {}
    for name in virtual_names:
        matched = re.search(VIP0_NAME_REGEX, name)

        if not matched:
            continue

        campus = matched.group(1)
        if campus in high_level_vips:
            continue

        vip = re.sub(r'\.0$', '', name)
        high_level_vips[campus] = vip

    return list(six.itervalues(high_level_vips))


def available_virtual_port(lbc, environment, search=None, port=None):
    """Get the next available port for the provided environment"""
    vips = get_vips(lbc, environment, search=None)
    vips_to_used_ports = in_use_lbendpoint_ports(environment, vips)

    # Since all VIPs will be setup with the same port, then just get one random
    # VIP to check for available ports
    random_vip = random.choice(vips)
    _LOGGER.debug('random_vip: %r', random_vip)

    if port and port in vips_to_used_ports.get(random_vip):
        raise PortInUseError(
            'The supplied port {} in {} is already in use'.format(
                port, environment
            )
        )

    if port is None:
        port = random.randint(ASSIGN_PORT_START, MAX_PORT_VALUE)

    # If this VIP hasn't even been set, then return right away
    if random_vip not in vips_to_used_ports:
        _LOGGER.info('random_vip %r is not in use, returning %r: %r',
                     random_vip, vips, port)
        return (vips, port)

    total_tries = 0
    while port in vips_to_used_ports.get(random_vip):
        port = random.randint(ASSIGN_PORT_START, MAX_PORT_VALUE)
        total_tries = total_tries + 1
        if total_tries >= (MAX_PORT_VALUE - ASSIGN_PORT_START):
            raise NoAvailablePortError(
                'No available ports in %s, using search %s' %
                (environment, search)
            )

    return (vips, port)


def group2lbendpoint(app_group):
    """Normalize app group to lbendpoint"""
    lbendpoint = copy.deepcopy(app_group)

    group_type = lbendpoint['group-type']
    if group_type not in ['lbendpoint', 'lbendpoint-tm2']:
        return None
    del lbendpoint['group-type']

    endpoints = lbendpoint.get('endpoints')
    if endpoints and isinstance(endpoints, list):
        # Always just take the first entry, as endpoints are stored as list
        lbendpoint['endpoint'] = lbendpoint['endpoints'][0]
        del lbendpoint['endpoints']

    data = lbendpoint.get('data')
    if not data:
        return lbendpoint
    del lbendpoint['data']

    data_dict = utils.equals_list2dict(data)
    for attr, func in six.iteritems(_LBENDPOINT_DATA_ATTRS[group_type]):
        value = data_dict.get(attr)
        if value:
            lbendpoint[attr] = func(value) if func else value

    return lbendpoint


def lbendpoint2group(lbendpoint, group_type='lbendpoint'):
    """Normalize lbendpoint to app group"""
    app_group = copy.deepcopy(lbendpoint)

    app_group['group-type'] = group_type
    app_group['data'] = []

    endpoint = app_group.get('endpoint')
    if endpoint:
        app_group['endpoints'] = [app_group['endpoint']]
        del app_group['endpoint']

    for attr in sorted(_LBENDPOINT_DATA_ATTRS[group_type]):
        value = app_group.get(attr)
        if value:
            if isinstance(value, list):
                app_group['data'].append(
                    '{}={}'.format(attr, ','.join(sorted(value)))
                )
            else:
                app_group['data'].append('{}={}'.format(attr, value))
            del app_group[attr]

    return app_group
