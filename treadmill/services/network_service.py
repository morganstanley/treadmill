"""Bridge based network management service."""

import errno
import logging
import os
import subprocess

from .. import logcontext as lc
from .. import netdev
from .. import vipfile
from .. import iptables

from ._base_service import BaseResourceServiceImpl

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


class NetworkResourceService(BaseResourceServiceImpl):
    """Network link resource service.
    """
    __slots__ = (
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

    def __init__(self, ext_device, ext_mtu=None, ext_speed=None):
        super(NetworkResourceService, self).__init__()

        self._vips = None
        self._devices = {}
        self._bridge_mtu = 0
        # Read external device info
        if ext_mtu is None:
            self.ext_mtu = netdev.dev_mtu(ext_device)
        else:
            self.ext_mtu = ext_mtu
        if ext_speed is None:
            self.ext_speed = netdev.dev_speed(ext_device)
        else:
            self.ext_speed = ext_speed

    def initialize(self, service_dir):
        super(NetworkResourceService, self).initialize(service_dir)
        # The <svcroot>/vips directory is used to allocate/de-allocate
        # container vips.
        vips_dir = os.path.join(service_dir, self._VIPS_DIR)
        # Initialize vips
        self._vips = vipfile.VipMgr(vips_dir, self._service_rsrc_dir)
        self._vips.garbage_collect()

        # TODO: We should cleanup IP <-> Environment assignments here
        #                as well for extra safety.

        need_init = False
        try:
            netdev.link_set_up(self._TM_DEV0)
            netdev.link_set_up(self._TM_DEV1)
            netdev.link_set_up(self._TMBR_DEV)

        except subprocess.CalledProcessError:
            need_init = True

        if need_init:
            # Reset the bridge
            self._bridge_initialize()
            # Initialize the vIP records
            self._vips.initialize()

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
            if resource not in self._devices:
                self._vips.free(resource, ip)
                continue
            self._devices[resource]['ip'] = ip

        # Mark all the above information as stale
        for device in self._devices:
            self._devices[device]['stale'] = True

    def synchronize(self):
        modified = False
        for app_unique_name in self._devices.keys():
            if not self._devices[app_unique_name].get('stale', False):
                continue

            modified = True
            # This is a stale device, destroy it.
            self.on_delete_request(app_unique_name)

        if not modified:
            return

        # Read bridge status
        self._bridge_mtu = netdev.dev_mtu(self._TMBR_DEV)

    def report_status(self):
        status = {
            'bridge_dev': self._TMBR_DEV,
            'bridge_mtu': self._bridge_mtu,
            'int_dev': self._TM_DEV0,
            'int_ip': self._TM_IP,
            'ext_mtu': self.ext_mtu,
            'ext_speed': self.ext_speed,
        }
        status['devices'] = self._devices
        return status

    def on_create_request(self, rsrc_id, rsrc_data):
        """
        :returns ``dict``:
            Network IP `vip`, network device `veth`, IP gateway `gateway`.
        """
        with lc.LogContext(_LOGGER, rsrc_id) as log:
            log.logger.debug('req: %r', rsrc_data)

            app_unique_name = rsrc_id
            environment = rsrc_data['environment']

            assert environment in set(['dev', 'qa', 'uat', 'prod']), \
                'Unknown environment: %r' % environment

            veth0, veth1 = _devive_from_rsrc_id(app_unique_name)

            if app_unique_name not in self._devices:
                # VIPs allocation (the owner is the resource link)
                ip = self._vips.alloc(rsrc_id)

                # We can now mark ip traffic as belonging to the requested
                # environment.
                iptables.add_mark_rule(ip, environment)

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
            else:
                # Re-read what IP we assigned before
                ip = self._devices[app_unique_name]['ip']

            # Record the new device in our state
            self._devices[app_unique_name] = _device_info(veth0)
            self._devices[app_unique_name].update(
                {
                    'ip': ip,
                    'environment': environment,
                }
            )

        result = {
            'vip': ip,
            'veth': veth1,
            'gateway': self._TM_IP,
        }
        return result

    def on_delete_request(self, rsrc_id):
        app_unique_name = rsrc_id

        with lc.LogContext(_LOGGER, rsrc_id):
            veth, _ = _devive_from_rsrc_id(app_unique_name)

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
                iptables.delete_mark_rule(
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
        except subprocess.CalledProcessError:
            pass

        try:
            netdev.link_set_down(self._TM_DEV0)
            netdev.link_del_veth(self._TM_DEV0)
        except subprocess.CalledProcessError:
            pass

        try:
            netdev.link_set_down(self._TMBR_DEV)
            netdev.bridge_delete(self._TMBR_DEV)
        except subprocess.CalledProcessError:
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


def _devive_from_rsrc_id(app_unique_name):
    """Format devices names.

    :returns:
        ``tuple`` - Pair for device names based on the app_unique_name.
    """
    # FIXME(boysson): This kind of manipulation should live elsewhere.
    _, uniqueid = app_unique_name.rsplit('-', 1)

    veth0 = '{id:>013s}.0'.format(id=uniqueid)
    veth1 = '{id:>013s}.1'.format(id=uniqueid)

    return (veth0, veth1)
