"""Higher level functions used to manage virtuals using LBControl2 API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket

from treadmill import exc

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms import lbendpoint


_LOGGER = logging.getLogger(__name__)

_DUMMY_SVC = lbendpoint.DUMMY_SVC


def _servicename_to_hostport(servicename):
    """Convert a service name into a host:port format."""
    shortname, _sep, port = servicename.partition('.tcp.')
    if not _sep:
        raise exc.TreadmillError('Invalid service name: %r' %
                                 (servicename,))
    return '{hostname}:{port}'.format(
        hostname=socket.getfqdn(shortname),
        port=port
    )


def _hostport_to_service(hostport):
    """Convert a hostport into a service dict."""
    hostname, _sep, port = hostport.partition(':')
    if not _sep:
        raise exc.TreadmillError('Invalid hostport: %r' %
                                 (hostport,))
    # Remove the default domain. This is required by the LBC API
    if hostname.endswith('.ms.com'):
        shortname = hostname[:-len('.ms.com')]
    else:
        shortname = hostname
        hostname = socket.getfqdn(hostname)

    return {
        'service_name': '{shortname}.tcp.{port}'.format(
            shortname=shortname,
            port=port,
        ),
        'hostname': hostname,
        'port': port,
    }


def get_pool_members(lbc, name, pool=None):
    """Get LB pool members (host:port format).
    """
    _LOGGER.info('Getting %s members', name)

    pool = pool or lbc.get_pool(name)
    if not pool:
        raise exc.TreadmillError('LB pool %s doesn\'t exist' % name)

    return {
        _servicename_to_hostport(member.service.name): member
        for member in pool.members
        if member.service.name != _DUMMY_SVC
    }


def edit_pool_members(lbc, name, to_add, to_rm, pool=None):
    """Add/remove LB pool members (host:port format)."""
    _LOGGER.info('Editing %s members, add: %r, rm: %r', name, to_add, to_rm)

    pool = pool or lbc.get_pool(name)
    if not pool:
        raise exc.TreadmillError('LB pool %s doesn\'t exist' % name)

    lbc.edit_pool_parameters(
        pool_name=name,
        virtual_name=name,
        lb_method=pool.lb_method or 'round_robin',
        min_active=pool.min_active,
        svc_down_action=pool.svc_down_action,
        svc_to_add=[_hostport_to_service(svc) for svc in to_add],
        svc_to_rm=[_hostport_to_service(svc) for svc in to_rm],
    )

    # Activate added members + any members that are not active (self-heal).
    not_active_pool_members = {
        _servicename_to_hostport(member.service.name)
        for member in pool.members
        if not member.active and member.service.name != _DUMMY_SVC
    }
    to_activate = set(to_add) | not_active_pool_members
    if to_activate:
        activate_pool_members(lbc, name, to_activate)


def update_pool_members(lbc, name, target_members, pool=None):
    """Update LB pool members (host:port format)."""
    _LOGGER.info('Updating %s members: %r', name, target_members)

    pool = pool or lbc.get_pool(name)
    if not pool:
        raise exc.TreadmillError('LB pool %s doesn\'t exist' % name)

    members = get_pool_members(lbc, name, pool=pool)

    to_add = set(target_members) - set(members)
    to_rm = set(members) - set(target_members)

    if to_add or to_rm:
        edit_pool_members(lbc, name, to_add, to_rm, pool=pool)


def activate_pool_members(lbc, name, to_activate):
    """Activate LB pool members (host:port format)."""
    _LOGGER.info('Activating %s members: %r', name, to_activate)

    lbc.modify_pool_member_state(
        virtual_name=name,
        pool_name=name,
        services=[_hostport_to_service(svc) for svc in to_activate],
        transition_type='ACTIVATE',
    )


def check_pool_health(lbc, name, fix=False):
    """Check LB pool health, activate members/push virtual to fix it."""
    _LOGGER.info('Checking %s health', name)

    status = {}
    to_activate = set()
    push_virtual = False

    members = get_pool_members(lbc, name)

    pool_health = lbc.virtual_pool_status(name, name)
    pool_health_members = {
        (svc.ip_addr, svc.port): svc.device_config_state
        for svc in pool_health.service_healths
    }

    for member in members:
        active = members[member].active
        service = members[member].service
        device_status = pool_health_members.get((service.ip, service.port))
        if not active:
            status[member] = 'Member is not active'
            to_activate.add(member)
        elif device_status != lbcontrol.DeviceConfigState.enabled:
            status[member] = 'Member is not enabled on the device'
            push_virtual = True
        else:
            status[member] = 'OK'

    if fix and to_activate:
        activate_pool_members(lbc, name, to_activate)
    if fix and push_virtual:
        lbc.push_virtual(name)

    # If the fix did something, return the status after fixing.
    if fix and (to_activate or push_virtual):
        return check_pool_health(lbc, name, fix=False)
    _LOGGER.info(status)
    return status
