"""Bridge based network management service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os

import six
import netifaces

from treadmill import iptables
from treadmill import logcontext as lc
from treadmill import netdev
from treadmill import subproc
from treadmill import vipfile

from . import BaseResourceServiceImpl

_LOGGER = logging.getLogger(__name__)

#: Container environment to ipset set.
_SET_BY_ENVIRONMENT = {
    'dev': iptables.SET_NONPROD_CONTAINERS,
    'qa': iptables.SET_NONPROD_CONTAINERS,
    'uat': iptables.SET_NONPROD_CONTAINERS,
    'prod': iptables.SET_PROD_CONTAINERS,
}


class NetworkResourceService(BaseResourceServiceImpl):
    """Network link resource service.
    """
    __slots__ = (
        'ext_device',
        'ext_ip',
        'ext_mtu',
        'ext_speed',
        '_bridge_mtu',
        '_devices',
        '_vips',
    )

    PAYLOAD_SCHEMA = (
        ('environment', True, str),
    )

    _VIPS_DIR = 'vips'
    _TMBR_DEV = 'br0'
    _TM_DEV0 = 'tm0'
    _TM_DEV1 = 'tm1'
    _TM_IP = '192.168.254.254'
    _TM_CIDR = '192.168.0.0/16'  # TODO: node cidr fixed for now

    def __init__(self, ext_device, ext_ip=None, ext_mtu=None, ext_speed=None):
        super(NetworkResourceService, self).__init__()

        self._vips = None
        self._devices = {}
        self._bridge_mtu = 0
        self.ext_device = ext_device
        # Read external device info
        if ext_mtu is None:
            self.ext_mtu = netdev.dev_mtu(ext_device)
        else:
            self.ext_mtu = ext_mtu
        if ext_speed is None:
            self.ext_speed = netdev.dev_speed(ext_device)
        else:
            self.ext_speed = ext_speed
        if ext_ip is None:
            self.ext_ip = _device_ip(ext_device)
        else:
            self.ext_ip = ext_ip

    def initialize(self, service_dir):
        super(NetworkResourceService, self).initialize(service_dir)
        # The <svcroot>/vips directory is used to allocate/de-allocate
        # container vips.
        vips_dir = os.path.join(service_dir, self._VIPS_DIR)
        # Initialize vips
        self._vips = vipfile.VipMgr(
            cidr=self._TM_CIDR,
            path=vips_dir,
            owner_path=self._service_rsrc_dir
        )
        # TODO: brige IP should be reserved to avoid possible assignment.

        # Clear all environment assignments here. They will be re-assigned
        # below.
        for containers_set in set(_SET_BY_ENVIRONMENT.values()):
            iptables.create_set(containers_set,
                                set_type='hash:ip',
                                family='inet', hashsize=1024, maxelem=65536)

        need_init = False
        try:
            netdev.link_set_up(self._TM_DEV0)
            netdev.link_set_up(self._TM_DEV1)
            netdev.link_set_up(self._TMBR_DEV)

        except subproc.CalledProcessError:
            need_init = True

        if need_init:
            # Reset the bridge
            self._bridge_initialize()

        # These two are also done here because they are idempotent
        # Disable bridge forward delay
        netdev.bridge_setfd(self._TMBR_DEV, 0)
        # Enable route_localnet so that we can redirect traffic from the
        # container to the node's loopback address.
        netdev.dev_conf_route_localnet_set(self._TM_DEV0, True)

        # Read bridge status
        self._bridge_mtu = netdev.dev_mtu(self._TMBR_DEV)

        # Read current status
        self._devices = {}
        for device in netdev.bridge_brif(self._TMBR_DEV):
            # Ignore local device that is used pass external traffic into the
            # Treadmill container network.
            if device == self._TM_DEV1:
                continue

            dev_info = _device_info(device)
            self._devices[dev_info['alias']] = dev_info

        # Read the currently assigned vIPs
        for (ip, resource) in self._vips.list():
            self._devices.setdefault(resource, {})['ip'] = ip

        # Mark all the above information as stale
        for device in self._devices:
            self._devices[device]['stale'] = True

    def synchronize(self):
        """Cleanup state resource.
        """
        for app_unique_name in six.viewkeys(self._devices.copy()):
            if not self._devices[app_unique_name].get('stale', False):
                continue

            # This is a stale device, destroy it.
            self.on_delete_request(app_unique_name)

        # Reset the container environment sets to the IP we have now cleaned
        # up.  This is more complex than expected because multiple environment
        # can be merged in the same set in _SET_BY_ENVIRONMENT.
        container_env_ips = {}
        for set_name in set(_SET_BY_ENVIRONMENT.values()):
            key = sorted(
                [
                    env for env in _SET_BY_ENVIRONMENT
                    if _SET_BY_ENVIRONMENT[env] == set_name
                ]
            )
            container_env_ips[tuple(key)] = set()

        for set_envs, set_ips in six.viewitems(container_env_ips):
            for device in six.viewvalues(self._devices):
                if device['environment'] not in set_envs:
                    continue
                set_ips.add(device['ip'])

        for set_envs, set_ips in six.viewitems(container_env_ips):
            iptables.atomic_set(
                _SET_BY_ENVIRONMENT[set_envs[0]],
                set_ips,
                set_type='hash:ip',
                family='inet', hashsize=1024, maxelem=65536
            )

        # It is now safe to clean up all remaining vIPs without resource.
        self._vips.garbage_collect()

        # Read bridge status
        self._bridge_mtu = netdev.dev_mtu(self._TMBR_DEV)

    def report_status(self):
        status = {
            'bridge_dev': self._TMBR_DEV,
            'bridge_mtu': self._bridge_mtu,
            'internal_device': self._TM_DEV0,
            'internal_ip': self._TM_IP,
            'external_device': self.ext_device,
            'external_ip': self.ext_ip,
            'external_mtu': self.ext_mtu,
            'external_speed': self.ext_speed,
        }
        status['devices'] = self._devices
        return status

    def on_create_request(self, rsrc_id, rsrc_data):
        """
        :returns ``dict``:
            Network IP `vip`, network device `veth`, IP gateway `gateway`.
        """
        with lc.LogContext(_LOGGER, rsrc_id,
                           adapter_cls=lc.ContainerAdapter) as log:
            log.debug('req: %r', rsrc_data)

            app_unique_name = rsrc_id
            environment = rsrc_data['environment']

            assert environment in _SET_BY_ENVIRONMENT, \
                'Unknown environment: %r' % environment

            veth0, veth1 = _device_from_rsrc_id(app_unique_name)

            if app_unique_name not in self._devices:
                # VIPs allocation (the owner is the resource link)
                ip = self._vips.alloc(rsrc_id)
                self._devices[app_unique_name] = {
                    'ip': ip
                }
            else:
                # Re-read what IP we assigned before
                ip = self._devices[app_unique_name]['ip']

            if 'device' not in self._devices[app_unique_name]:
                # Create the interface pair
                netdev.link_add_veth(veth0, veth1)
                # Configure the links
                netdev.link_set_mtu(veth0, self.ext_mtu)
                netdev.link_set_mtu(veth1, self.ext_mtu)
                # Tag the interfaces
                netdev.link_set_alias(veth0, rsrc_id)
                netdev.link_set_alias(veth1, rsrc_id)
                # Add interface to the bridge
                netdev.bridge_addif(self._TMBR_DEV, veth0)
                netdev.link_set_up(veth0)
                # We keep veth1 down until inside the container

            # Record the new device in our state
            self._devices[app_unique_name] = _device_info(veth0)
            self._devices[app_unique_name].update(
                {
                    'ip': ip,
                    'environment': environment,
                }
            )

            # We can now mark ip traffic as belonging to the requested
            # environment.
            _add_mark_rule(ip, environment)

        result = {
            'vip': ip,
            'veth': veth1,
            'gateway': self._TM_IP,
            'external_ip': self.ext_ip,
        }
        return result

    def on_delete_request(self, rsrc_id):
        app_unique_name = rsrc_id

        with lc.LogContext(_LOGGER, rsrc_id):
            veth, _ = _device_from_rsrc_id(app_unique_name)

            try:
                netdev.dev_state(veth)
                netdev.link_del_veth(veth)

            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise

            # Remove it from our state (if present)
            dev_info = self._devices.pop(app_unique_name, None)
            if dev_info is not None and 'ip' in dev_info:
                # Remove the environment mark on the IP
                if 'environment' in dev_info:
                    _delete_mark_rule(
                        dev_info['ip'],
                        dev_info['environment']
                    )
                # VIPs deallocation (the owner is the resource link)
                self._vips.free(app_unique_name, dev_info['ip'])

        return True

    def _bridge_initialize(self):
        """Reset/initialize the Treadmill node bridge.
        """
        try:
            # FIXME(boysson): This is for migration when TM_DEV0 used to be a
            #                 bridge.
            netdev.link_set_down(self._TM_DEV0)
            netdev.bridge_delete(self._TM_DEV0)
        except subproc.CalledProcessError:
            pass

        try:
            netdev.link_set_down(self._TM_DEV0)
            netdev.link_del_veth(self._TM_DEV0)
        except subproc.CalledProcessError:
            pass

        try:
            netdev.link_set_down(self._TMBR_DEV)
            netdev.bridge_delete(self._TMBR_DEV)
        except subproc.CalledProcessError:
            pass

        netdev.bridge_create(self._TMBR_DEV)
        netdev.bridge_setfd(self._TMBR_DEV, 0)
        netdev.link_add_veth(self._TM_DEV0, self._TM_DEV1)
        netdev.link_set_mtu(self._TM_DEV0, self.ext_mtu)
        netdev.link_set_mtu(self._TM_DEV1, self.ext_mtu)
        netdev.bridge_addif(self._TMBR_DEV, self._TM_DEV1)
        # Force the bridge MAC address to the Treadmill device. This
        # prevents the bridge's MAC from changing when adding/removing
        # container interfaces.
        # (Default Linux bridge behavior is to set the bridge's MAC to be
        # lowest of it's ports).
        tm_mac = netdev.dev_mac(self._TM_DEV1)
        netdev.link_set_addr(self._TMBR_DEV, tm_mac)
        # Bring up the bridge interface
        netdev.link_set_up(self._TMBR_DEV)
        netdev.link_set_up(self._TM_DEV1)
        netdev.addr_add(
            addr='{ip}/16'.format(ip=self._TM_IP),
            devname=self._TM_DEV0
        )
        # Enable route_localnet so that we can redirect traffic from the
        # container to the node's loopback address.
        netdev.dev_conf_route_localnet_set(self._TM_DEV0, True)
        # Bring up the TM interface
        netdev.link_set_up(self._TM_DEV0)


def _device_info(device):
    """Gather a given device information.
    """
    return {
        'device': device,
        'mtu': netdev.dev_mtu(device),
        'speed': netdev.dev_speed(device),
        'alias': netdev.dev_alias(device),
    }


def _device_from_rsrc_id(app_unique_name):
    """Format devices names.

    :returns:
        ``tuple`` - Pair for device names based on the app_unique_name.
    """
    # FIXME: This kind of manipulation should live elsewhere.
    _, uniqueid = app_unique_name.rsplit('-', 1)

    veth0 = '{id:>013s}.0'.format(id=uniqueid)
    veth1 = '{id:>013s}.1'.format(id=uniqueid)

    return (veth0, veth1)


def _device_ip(device):
    """Return the IPv4 address assigned to a give device.

    :param ``str``:
        Device name
    :returns:
        ``str`` - IPv4 address of the device
    """
    ifaddresses = netifaces.ifaddresses(device)
    # FIXME: We are making an assumption and always taking the first IPv4
    #        assigned to the device.
    return ifaddresses[netifaces.AF_INET][0]['addr']


def _add_mark_rule(src_ip, environment):
    """Add an environment mark for all traffic coming from an IP.

    :param ``str`` src_ip:
        Source IP to be marked
    :param ``str`` environment:
        Environment to use for the mark
    """
    assert environment in _SET_BY_ENVIRONMENT, \
        'Unknown environment: %r' % environment

    target_set = _SET_BY_ENVIRONMENT[environment]
    iptables.add_ip_set(target_set, src_ip)

    # Check that the IP is not marked in any other environment
    other_env_sets = {
        env_set for env_set in six.viewvalues(_SET_BY_ENVIRONMENT)
        if env_set != target_set
    }
    for other_set in other_env_sets:
        if iptables.test_ip_set(other_set, src_ip) is True:
            raise Exception('%r is already in %r' % (src_ip, other_set))


def _delete_mark_rule(src_ip, environment):
    """Remove an environment mark from a source IP.

    :param ``str`` src_ip:
        Source IP on which the mark is set.
    :param ``str`` environment:
        Environment to use for the mark
    """
    assert environment in _SET_BY_ENVIRONMENT, \
        'Unknown environment: %r' % environment

    target_set = _SET_BY_ENVIRONMENT[environment]
    iptables.rm_ip_set(target_set, src_ip)
