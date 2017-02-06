"""Network device management."""

import errno
import os
import logging

import enum

from . import subproc


_LOGGER = logging.getLogger(__name__)

_SYSFS_NET = '/sys/class/net'
_BRCTL_EXE = 'brctl'
_IP_EXE = 'ip'

_PROC_CONF_PROXY_ARP = '/proc/sys/net/ipv4/conf/{dev}/proxy_arp'
_PROC_CONF_FORWARDING = '/proc/sys/net/ipv4/conf/{dev}/forwarding'
_PROC_CONF_ARP_IGNORE = '/proc/sys/net/ipv4/conf/{dev}/arp_ignore'
_PROC_CONF_ROUTE_LOCALNET = '/proc/sys/net/ipv4/conf/{dev}/route_localnet'


def dev_mtu(devname):
    """Read a device's MTU.

    :param ``str`` devname:
        The name of the network device.
    :returns:
        ``int`` - Device MTU
    :raises:
        OSError, IOError if the device doesn't exist
    """
    return int(_get_dev_attr(devname, 'mtu'))


def dev_mac(devname):
    """Read a device's MAC address.

    :param ``str`` devname:
        The name of the network device.
    :returns:
        ``str`` - Device MAC address
    :raises:
        OSError, IOError if the device doesn't exist
    """
    return str(_get_dev_attr(devname, 'address'))


def dev_alias(devname):
    """Read a device's defined alias.

    :param ``str`` devname:
        The name of the network device.
    :returns:
        ``str`` - Device alias
    :raises:
        OSError, IOError if the device doesn't exist
    """
    return str(_get_dev_attr(devname, 'ifalias'))


class DevState(enum.Enum):
    """Network device state.

    https://www.kernel.org/doc/Documentation/networking/operstates.txt
    """
    # Class has no __init__ method
    # pylint: disable=W0232

    UP = b'up'  # pylint: disable=C0103
    DOWN = b'down'
    UNKNOWN = b'unknown'
    LOWERLAYERDOWN = b'lowerlayerdown'


def dev_state(devname):
    """Read a device's state.

    :param ``str`` devname:
        The name of the network device.
    :returns:
        ``DevState`` - Device state
    :raises:
        OSError, IOError if the device doesn't exist
    """
    return DevState(_get_dev_attr(devname, 'operstate'))


def dev_speed(devname):
    """Read a device's link speed.

    :param ``str`` devname:
        The name of the network device.
    :returns:
        ``int`` -  Device link speed
    :raises:
        OSError, IOError (ENOENT) if the device doesn't exist
    """
    try:
        return int(_get_dev_attr(devname, 'speed'))
    except IOError as err:
        if err.errno == errno.EINVAL:
            _LOGGER.warn('Unable to read speed information from %s', devname)
            return 0


def link_set_up(devname):
    """Bring a network device up.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'up'
        ],
    )


def link_set_down(devname):
    """Bring a network device down.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'down'
        ],
    )


def link_set_name(devname, newname):
    """Set a network device's name.

    :param ``str`` devname:
        The current name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'name', newname,
        ],
    )


def link_set_alias(devname, alias):
    """Set a network device's alias.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'alias', alias,
        ],
    )


def link_set_mtu(devname, mtu):
    """Set a network device's MTU.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'mtu', str(mtu),
        ],
    )


def link_set_netns(devname, namespace):
    """Set a network device's namespace.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'netns', str(namespace),
        ],
    )


def link_set_addr(devname, macaddr):
    """Set mac address of the link

    :param ``str`` devname:
        The name of the network device.
    :param ``str`` macaddr:
        The mac address.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'set',
            'dev', devname,
            'address', macaddr,
        ],
    )


def link_add_veth(veth0, veth1):
    """Create a virtual ethernet device pair.

    :param ``str`` veth0:
        The name of the first network device.
    :param ``str`` veth1:
        The name of the second network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'add', 'name', veth0,
            'type', 'veth',
            'peer', 'name', veth1
        ],
    )


def link_del_veth(devname):
    """Delete a virtual ethernet device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _IP_EXE, 'link',
            'delete',
            'dev', devname,
            'type', 'veth',
        ],
    )


def addr_add(addr, devname, addr_scope='link'):
    """Add an IP address to a network device.

    :param ``str`` addr:
        IP address.
    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            'ip', 'addr',
            'add',
            addr,
            'dev', devname,
            'scope', addr_scope,
        ],
    )


def route_add(dest, via=None, devname=None, src=None, route_scope=None):
    """Define a new entry in the routing table.

    :param ``str`` devname:
        The name of the network device.
    """
    assert devname or via
    route = [
        'ip', 'route',
        'add', dest,
    ]
    if via is not None:
        route += ['via', via]
    if devname is not None:
        route += ['dev', devname]
    if src is not None:
        route += ['src', src]
    if route_scope is not None:
        route += ['scope', route_scope]

    subproc.check_call(route)


def bridge_create(devname):
    """Create a new network bridge device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _BRCTL_EXE,
            'addbr',
            devname
        ],
    )


def bridge_delete(devname):
    """Delete a new network bridge device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _BRCTL_EXE,
            'delbr',
            devname
        ],
    )


def bridge_setfd(devname, forward_delay):
    """Configure the forward-delay of a bridge device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _BRCTL_EXE,
            'setfd',
            devname,
            str(forward_delay),
        ],
    )


def bridge_addif(devname, interface):
    """Add an interface to a bridge device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _BRCTL_EXE,
            'addif',
            devname,
            interface,
        ],
    )


def bridge_delif(devname, interface):
    """Remove an interface from a bridge device.

    :param ``str`` devname:
        The name of the network device.
    """
    subproc.check_call(
        [
            _BRCTL_EXE,
            'delif',
            devname,
            interface,
        ],
    )


def bridge_forward_delay(devname):
    """Read a bridge device's forward delay timer.

    :returns ``int``:
        Bridge forward delay timer.
    :raises:
        OSError, IOError (ENOENT) if the device doesn't exist.
    """
    return int(_get_dev_attr(devname, 'bridge/forward_delay'))


def bridge_brif(devname):
    """Read a bridge device's slave devices.

    :returns ``list``:
        List of slave device names.
    :raises:
        OSError, IOError (ENOENT) if the device doesn't exist or if the device
        is not a bridge.
    """
    return list(_get_dev_attr(devname, 'brif', dirattr=True))


def _get_dev_attr(devname, attr, dirattr=False):
    """
    :raises:
        OSError, IOError if the device doesn't exist
    """
    path = os.path.join(_SYSFS_NET, devname, attr)
    if dirattr:
        attr = os.listdir(path)
    else:
        with open(path) as f:
            attr = f.read().strip()

    return attr


def dev_conf_route_localnet_set(eth, enabled):
    """Enable Route Localnet on the given device

    :param ``str`` eth:
        The name of the ethernet device.
    :param ``bool`` enabled:
        Enable or disable the feature.
    """
    _proc_sys_write(
        _PROC_CONF_ROUTE_LOCALNET.format(dev=eth),
        int(enabled),
    )


def dev_conf_proxy_arp_set(eth, enabled):
    """Enable Proxy-Arp on the given device

    :param ``str`` eth:
        The name of the ethernet device.
    :param ``bool`` enabled:
        Enable or disable the feature.
    """
    _proc_sys_write(
        _PROC_CONF_PROXY_ARP.format(dev=eth),
        int(enabled),
    )


def dev_conf_forwarding_set(eth, enabled):
    """Enable IP Forwarding on the given device

    :param ``str`` eth:
        The name of the ethernet device.
    :param ``bool`` enabled:
        Enable or disable the feature.
    """
    _proc_sys_write(
        _PROC_CONF_FORWARDING.format(dev=eth),
        int(enabled),
    )


# FIXME(boysson): Should be an enum
# Reply for any local target IP address, configured on any interface
ARP_IGNORE_REPLY_ANY_LOCAL = 0
# Do not reply for local addresses configured with scope host, only resolutions
# for global and link addresses are replied
ARP_IGNORE_DO_NOT_REPLY_ANY_ON_HOST = 3


def dev_conf_arp_ignore_set(eth, value):
    """Set the arp_ignore flag on the given device

    Define different modes for sending replies in response to received ARP
    requests that resolve local target IP addresses

    :param ``str`` eth:
        The name of the ethernet device.
    :param ``int`` value:
        Set arp_ignore to this value.
    """
    _proc_sys_write(
        _PROC_CONF_ARP_IGNORE.format(dev=eth),
        int(value),
    )


def _proc_sys_write(path, value):
    """Set a sysctl value to `value`.
    """
    assert path.startswith('/proc/sys/')

    _LOGGER.debug('Setting %r to %r', path, value)
    with open(path, 'w') as f:
        f.write(str(value))
