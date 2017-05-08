"""Manage Treadmill vIPs allocations"""


import errno

import glob
import logging
import os

from . import fs


_LOGGER = logging.getLogger(__name__)


class VipMgr(object):
    """VIP allocation manager.

    :param basepath:
        Base directory that will contain all the allocated VIPs.
    :type basepath:
        ``str``
    """
    __slots__ = (
        '_base_path',
        '_owner_path',
    )

    def __init__(self, path, owner_path):
        # Make sure vips directory exists.
        fs.mkdir_safe(path)
        self._base_path = os.path.realpath(path)
        self._owner_path = os.path.realpath(owner_path)

    def initialize(self):
        """Initialize the vip folder."""
        map(os.unlink, glob.glob(os.path.join(self._base_path, '*')))

    def alloc(self, owner, picked_ip=None):
        """Atomically allocates virtual IP pair for the container.
        """
        if picked_ip is not None:
            if not self._alloc(owner, picked_ip):
                raise Exception('Unabled to assign IP %r for %r',
                                picked_ip, owner)
            return picked_ip

        for index in range(0, 256**2):
            major, minor = (index >> 8), (index % 256)
            if major in [128, 256]:
                continue
            if minor in [0, 256]:
                continue
            ip = '192.168.{major}.{minor}'.format(major=major, minor=minor)
            if not self._alloc(owner, ip):
                continue
            # We were able to grab the IP.
            break

        else:
            raise Exception('Unabled to find free IP for %r', owner)

        return ip

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
        allocated = glob.glob(
            os.path.join(self._base_path, '*')
        )
        for link in allocated:
            try:
                _link_st = os.stat(link)  # noqa: F841
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
        allocated = glob.glob(
            os.path.join(self._base_path, '*')
        )
        for link in allocated:
            try:
                ip_owner = os.readlink(link)
            except OSError as err:
                if err.errno == errno.EINVAL:
                    # not a link
                    continue
                raise
            ips.append((os.path.basename(link), os.path.basename(ip_owner)))

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
