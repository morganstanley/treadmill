"""LVM based local disk management service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import math
import os

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import cgroups
from treadmill import cgutils
from treadmill import localdiskutils
from treadmill import logcontext as lc
from treadmill import lvm
from treadmill import utils

from ._base_service import BaseResourceServiceImpl

_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))


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
        '_vg_status',
        '_volumes',
    )

    PAYLOAD_SCHEMA = (
        ('size', True, str),
    )

    def __init__(self, block_dev, read_bps, write_bps, read_iops, write_iops,
                 default_read_bps='20M', default_write_bps='20M',
                 default_read_iops=100, default_write_iops=100):
        super(LocalDiskResourceService, self).__init__()

        self._block_dev = block_dev
        self._read_bps = read_bps
        self._write_bps = write_bps
        self._read_iops = read_iops
        self._write_iops = write_iops
        self._vg_status = {}
        self._volumes = {}
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
        localdiskutils.setup_device_lvm(self._block_dev)

        # Finally retrieve the LV info
        lvs_info = lvm.lvsdisplay(group=localdiskutils.TREADMILL_VG)

        # Mark all retrived volume as 'stale'
        for lv in lvs_info:
            lv['stale'] = True
            if lv['open_count']:
                _LOGGER.warning('Logical volume in use: %r', lv['block_dev'])

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
        self._vg_status = localdiskutils.refresh_vg_status(
            localdiskutils.TREADMILL_VG
        )

    def synchronize(self):
        """Make sure that all stale volumes are removed.
        """
        modified = False
        for uniqueid in six.viewkeys(self._volumes.copy()):
            if not self._volumes[uniqueid].pop('stale', False):
                continue
            modified = True
            # This is a stale volume, destroy it.
            self._destroy_volume(uniqueid)

        if not modified:
            return

        # Now that we successfully removed a volume, retry all the pending
        # resources.
        for pending_id in self._pending:
            self._retry_request(pending_id)
        self._pending = []

        # We just destroyed a volume, refresh cached status from LVM and notify
        # the service of the availability of the new status.
        self._vg_status = localdiskutils.refresh_vg_status(
            localdiskutils.TREADMILL_VG
        )

    def report_status(self):
        return dict(list(self._vg_status.items()) + list({
            'read_bps': self._read_bps,
            'write_bps': self._write_bps,
            'read_iops': self._read_iops,
            'write_iops': self._write_iops
        }.items()))

    def on_create_request(self, rsrc_id, rsrc_data):
        app_unique_name = rsrc_id
        size = rsrc_data['size']
        read_bps = self._default_read_bps
        write_bps = self._default_write_bps
        read_iops = self._default_read_iops
        write_iops = self._default_write_iops

        with lc.LogContext(_LOGGER, rsrc_id) as log:
            log.logger.info('Processing request')

            size_in_bytes = utils.size_to_bytes(size)
            # FIXME(boysson): This kind of manipulation should live elsewhere.
            _, uniqueid = app_unique_name.rsplit('-', 1)

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
                    group=localdiskutils.TREADMILL_VG,
                    size_in_bytes=size_in_bytes,
                )
                # We just created a volume, refresh cached status from LVM
                self._vg_status = localdiskutils.refresh_vg_status(
                    localdiskutils.TREADMILL_VG
                )

            lv_info = lvm.lvdisplay(
                volume=uniqueid,
                group=localdiskutils.TREADMILL_VG
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
            # FIXME(boysson): This kind of manipulation should live elsewhere.
            _, uniqueid = app_unique_name.rsplit('-', 1)

            # Remove it from state (if present)
            if not self._destroy_volume(uniqueid):
                return

            # Now that we successfully removed a volume, retry all the pending
            # resources.
            for pending_id in self._pending:
                self._retry_request(pending_id)
            self._pending = []

            # We just destroyed a volume, refresh cached status from LVM and
            # notify the service of the availability of the new status.
            self._vg_status = localdiskutils.refresh_vg_status(
                localdiskutils.TREADMILL_VG
            )

        return True

    def _destroy_volume(self, uniqueid):
        """Try destroy a volume from LVM.
        """
        # Remove it from state (if present)
        self._volumes.pop(uniqueid, None)
        try:
            lvm.lvremove(uniqueid, group=localdiskutils.TREADMILL_VG)
        except subprocess.CalledProcessError:
            _LOGGER.warning('Ignoring unknow volume %r', uniqueid)
            return False

        _LOGGER.info('Destroyed volume %r', uniqueid)
        return True

    def _retry_request(self, rsrc_id):
        """Force re-evaluation of a request.
        """
        # XXX(boysson): Duplicate of _base_service.clt_update_request
        request_lnk = os.path.join(self._service_rsrc_dir, rsrc_id)
        _LOGGER.debug('Updating %r', rsrc_id)
        # NOTE(boysson): This does the equivalent of a touch on the symlink
        try:
            os.lchown(
                request_lnk,
                os.getuid(),
                os.getgid()
            )
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
