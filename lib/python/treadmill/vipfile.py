"""Manage Treadmill vIPs allocations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import ipaddress  # pylint: disable=wrong-import-order
import logging
import os

from treadmill import fs


_LOGGER = logging.getLogger(__name__)


class VipMgr:
    """VIP allocation manager.
    """
    __slots__ = (
        '_base_path',
        '_cidr',
        '_owner_path',
    )

    def __init__(self, cidr, path, owner_path):
        """
        :param ``str`` cidr:
            CIDR to allocate IPs from.
        :param ``str`` path:
            Base directory that will contain all the allocated VIPs.
        :param ``str`` owner_path:
            Directory that will contain all the VIPs owners.
        """
        self._cidr = ipaddress.IPv4Network(cidr)
        # Make sure vips directory exists.
        fs.mkdir_safe(path)
        self._base_path = os.path.realpath(path)
        self._owner_path = os.path.realpath(owner_path)

    def initialize(self):
        """Initialize the vip folder.

        Remove any IP we own from our base path.
        """
        for vip in os.listdir(self._base_path):
            try:
                vip_addr = ipaddress.ip_address(vip)
            except ValueError:
                # Not an IP
                continue
            if vip_addr in self._cidr:
                try:
                    os.unlink(os.path.join(self._base_path, vip))
                except OSError as err:
                    if err.errno == errno.ENOENT:
                        continue
                    raise

    def alloc(self, owner, picked_ip=None):
        """Atomically allocates virtual IP pair for the container.

        :returns:
            ``str`` - Allocated IPv4 address.
        """
        if picked_ip is not None:
            if ipaddress.IPv4Address(picked_ip) not in self._cidr:
                raise ValueError('IP not in CIDR')
            if not self._alloc(owner, picked_ip):
                raise Exception(
                    'Unable to assign IP %r for %r' % (picked_ip, owner)
                )
            return picked_ip

        for vip in self._cidr.hosts():
            vip = str(vip)  # Convert IPv*Address to string
            if not self._alloc(owner, vip):
                continue
            # We were able to grab the IP.
            break

        else:
            vip = None  # Assure pylint this variable is set
            raise Exception('Unable to find a free IP for %r' % owner)

        return vip

    def free(self, owner, owned_ip):
        """Atomically frees virtual IP associated with the container.
        """
        path = os.path.join(self._base_path, owned_ip)
        try:
            ip_owner = os.path.basename(os.readlink(path))
            if ip_owner != owner:
                _LOGGER.critical('%r tried to free %r that it does not own',
                                 owner, owned_ip)
                return
            os.unlink(path)
            _LOGGER.debug('Freed %r', owned_ip)

        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.exception('Freed unallocated ip %r', owned_ip)
            else:
                raise

    def garbage_collect(self):
        """Garbage collect all VIPs without owner.
        """
        for vip in os.listdir(self._base_path):
            link = os.path.join(self._base_path, vip)
            try:
                _link_st = os.stat(link)
            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning('Reclaimed: %r', link)
                    try:
                        os.unlink(link)
                    except OSError as err:
                        if err.errno == errno.ENOENT:
                            pass
                        else:
                            raise
                else:
                    raise

    def list(self):
        """List all allocated IPs and their owner
        """
        ips = []
        for vip in os.listdir(self._base_path):
            link = os.path.join(self._base_path, vip)
            try:
                ip_owner = os.readlink(link)
            except OSError as err:
                if err.errno == errno.EINVAL:
                    # not a link
                    continue
                raise
            ips.append((vip, os.path.basename(ip_owner)))

        return ips

    def _alloc(self, owner, new_ip):
        """Atomaticly grab an IP for an owner.
        """
        ip_file = os.path.join(self._base_path, new_ip)
        owner_file = os.path.join(self._owner_path, owner)
        try:
            os.symlink(os.path.relpath(owner_file, self._base_path), ip_file)
            _LOGGER.debug('Allocated %r for %r', new_ip, owner)
        except OSError as err:
            if err.errno == errno.EEXIST:
                return False
            raise
        return True
