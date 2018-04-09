"""LVM based local disk management service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import math
import os

import six

from treadmill import cgroups
from treadmill import cgutils
from treadmill import localdiskutils
from treadmill import logcontext as lc
from treadmill import lvm
from treadmill import subproc
from treadmill import utils

from . import BaseResourceServiceImpl

_LOGGER = logging.getLogger(__name__)

TREADMILL_LV_PREFIX = 'tm-'


def _uniqueid(app_unique_name):
    """Create unique volume name based on unique app name.
    """
    _, uniqueid = app_unique_name.rsplit('-', 1)
    return TREADMILL_LV_PREFIX + uniqueid


class LocalDiskResourceService(BaseResourceServiceImpl):
    """LocalDisk service implementation.
    """

    __slots__ = (
        '_block_dev',
        '_read_bps',
        '_write_bps',
        '_read_iops',
        '_write_iops',
        '_default_read_bps',
        '_default_read_iops',
        '_default_write_bps',
        '_default_write_iops',
        '_pending',
        '_vg_name',
        '_vg_status',
        '_volumes',
        '_extent_reserved',
    )

    PAYLOAD_SCHEMA = (
        ('size', True, str),
    )

    def __init__(self, block_dev, vg_name,
                 read_bps, write_bps, read_iops, write_iops,
                 default_read_bps='20M', default_write_bps='20M',
                 default_read_iops=100, default_write_iops=100):
        super(LocalDiskResourceService, self).__init__()

        self._block_dev = block_dev
        self._read_bps = read_bps
        self._write_bps = write_bps
        self._read_iops = read_iops
        self._write_iops = write_iops
        self._vg_name = vg_name
        self._vg_status = {}
        self._volumes = {}
        self._extent_reserved = 0
        self._pending = []
        # TODO: temp solution - throttle read/writes to
        #                20M/s. In the future, IO will become part
        #                of app manifest spec and managed by
        #                scheduler same way as other resources.
        # TODO: Added IOps limit as well.
        self._default_read_bps = default_read_bps
        self._default_write_bps = default_write_bps
        self._default_read_iops = default_read_iops
        self._default_write_iops = default_write_iops

    def initialize(self, service_dir):
        super(LocalDiskResourceService, self).initialize(service_dir)

        # Make sure LVM Volume Group set up
        localdiskutils.setup_device_lvm(self._block_dev, self._vg_name)

        # Finally retrieve the LV info
        lvs_info = lvm.lvsdisplay(group=self._vg_name)

        # Mark all retrived volumes that were created by treadmill as 'stale'
        for lv in lvs_info:
            lv['stale'] = lv['name'].startswith(TREADMILL_LV_PREFIX)
            if lv['open_count']:
                _LOGGER.warning('Logical volume in use: %r', lv['block_dev'])

        # Count the number of extents taken by non-treadmill volumes
        self._extent_reserved = sum([
            lv['extent_size'] for lv in lvs_info if not lv['stale']
        ])

        volumes = {
            lv['name']: {
                k: lv[k]
                for k in [
                    'name', 'block_dev',
                    'dev_major', 'dev_minor',
                    'extent_size',
                    'stale',
                ]
            }
            for lv in lvs_info
        }
        self._volumes = volumes
        self._vg_status = localdiskutils.refresh_vg_status(self._vg_name)

    def synchronize(self):
        """Make sure that all stale volumes are removed.
        """
        modified = False
        for uniqueid in six.viewkeys(self._volumes.copy()):
            if self._volumes[uniqueid].pop('stale', False):
                modified = True
                # This is a stale volume, destroy it.
                self._destroy_volume(uniqueid)

        if not modified:
            return

        # Now that we successfully removed a volume, retry all the pending
        # resources.
        for pending_id in self._pending:
            self.retry_request(pending_id)
        self._pending = []

        # We just destroyed a volume, refresh cached status from LVM and notify
        # the service of the availability of the new status.
        self._vg_status = localdiskutils.refresh_vg_status(self._vg_name)

    def report_status(self):
        status = self._vg_status.copy()
        extent_avail = status['extent_nb'] - self._extent_reserved
        status['size'] = extent_avail * status['extent_size']
        status.update({
            'read_bps': self._read_bps,
            'write_bps': self._write_bps,
            'read_iops': self._read_iops,
            'write_iops': self._write_iops
        })
        return status

    def on_create_request(self, rsrc_id, rsrc_data):
        app_unique_name = rsrc_id
        size = rsrc_data['size']
        read_bps = self._default_read_bps
        write_bps = self._default_write_bps
        read_iops = self._default_read_iops
        write_iops = self._default_write_iops

        with lc.LogContext(_LOGGER, rsrc_id,
                           adapter_cls=lc.ContainerAdapter) as log:
            log.info('Processing request')

            size_in_bytes = utils.size_to_bytes(size)
            uniqueid = _uniqueid(app_unique_name)

            # Create the logical volume
            existing_volume = uniqueid in self._volumes
            if not existing_volume:
                needed = math.ceil(
                    size_in_bytes / self._vg_status['extent_size']
                )
                if needed > self._vg_status['extent_free']:
                    # If we do not have enough space, delay the creation until
                    # another volume is deleted.
                    log.info(
                        'Delaying request %r until %d extents are free.'
                        ' Current volumes: %r',
                        rsrc_id, needed, self._volumes)
                    self._pending.append(rsrc_id)
                    return None

                lvm.lvcreate(
                    volume=uniqueid,
                    group=self._vg_name,
                    size_in_bytes=size_in_bytes,
                )
                # We just created a volume, refresh cached status from LVM
                self._vg_status = localdiskutils.refresh_vg_status(
                    self._vg_name
                )

            lv_info = lvm.lvdisplay(
                volume=uniqueid,
                group=self._vg_name
            )

            # Configure block device using cgroups (this is idempotent)
            # FIXME(boysson): The unique id <-> cgroup relation should be
            #                 captured in the cgroup module.
            cgrp = os.path.join('treadmill', 'apps', app_unique_name)
            cgutils.create('blkio', cgrp)
            major, minor = lv_info['dev_major'], lv_info['dev_minor']
            cgroups.set_value(
                'blkio', cgrp,
                'blkio.throttle.write_bps_device',
                '{major}:{minor} {bps}'.format(
                    major=major,
                    minor=minor,
                    bps=utils.size_to_bytes(write_bps),
                )
            )
            cgroups.set_value(
                'blkio', cgrp,
                'blkio.throttle.read_bps_device',
                '{major}:{minor} {bps}'.format(
                    major=major,
                    minor=minor,
                    bps=utils.size_to_bytes(read_bps),
                )
            )
            cgroups.set_value(
                'blkio', cgrp,
                'blkio.throttle.write_iops_device',
                '{major}:{minor} {iops}'.format(
                    major=major,
                    minor=minor,
                    iops=write_iops
                )
            )
            cgroups.set_value(
                'blkio', cgrp,
                'blkio.throttle.read_iops_device',
                '{major}:{minor} {iops}'.format(
                    major=major,
                    minor=minor,
                    iops=read_iops
                )
            )

            volume_data = {
                k: lv_info[k]
                for k in ['name', 'block_dev',
                          'dev_major', 'dev_minor', 'extent_size']
            }

            # Record existence of the volume.
            self._volumes[lv_info['name']] = volume_data

        return volume_data

    def on_delete_request(self, rsrc_id):
        app_unique_name = rsrc_id

        with lc.LogContext(_LOGGER, rsrc_id):
            uniqueid = _uniqueid(app_unique_name)

            # Remove it from state (if present)
            if not self._destroy_volume(uniqueid):
                return False

            # Now that we successfully removed a volume, retry all the pending
            # resources.
            for pending_id in self._pending:
                self.retry_request(pending_id)
            self._pending = []

            # We just destroyed a volume, refresh cached status from LVM and
            # notify the service of the availability of the new status.
            self._vg_status = localdiskutils.refresh_vg_status(self._vg_name)

        return True

    def _destroy_volume(self, uniqueid):
        """Try destroy a volume from LVM.
        """
        # Remove it from state (if present)
        self._volumes.pop(uniqueid, None)
        try:
            lvm.lvdisplay(uniqueid, group=self._vg_name)
        except subproc.CalledProcessError:
            _LOGGER.warning('Ignoring unknown volume %r', uniqueid)
            return False

        # This should not fail.
        lvm.lvremove(uniqueid, group=self._vg_name)
        _LOGGER.info('Destroyed volume %r', uniqueid)

        return True
