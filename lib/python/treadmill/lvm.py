"""Linux Volume Manager operations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import re

from . import subproc


_LOGGER = logging.getLogger(__name__)

_LVCREATE_EEXISTS_MSG_RE = re.compile(
    r'^  Logical volume "[^\"]+" already exists in volume group "[^\"]+"$'
)


###############################################################################
def pvcreate(device):
    """Create a new LVM physical volume.
    """
    return subproc.check_call(
        [
            'lvm',
            'pvcreate',
            '--force',
            '--yes',
            device,
        ]
    )


###############################################################################
def pvremove(device):
    """Remove LVM physical volume.
    """
    return subproc.check_call(
        [
            'lvm',
            'pvremove',
            '--force',
            device,
        ]
    )


###############################################################################
def pvdisplay():
    """Gather LVM physical volume information.
    """
    cmd = [
        'lvm',
        'pvdisplay',
        '--colon',
    ]

    info = subproc.check_output(cmd)
    info_data = [
        line.strip().split(':')
        for line in info.strip().split('\n')
        if line
    ]

    # The values are:
    #
    # 1  physical volume device name
    # 2  volume group name
    # 3  physical volume size in kilobytes
    # 4  internal physical volume number (obsolete)
    # 5  physical volume status
    # 6  physical volume (not) allocatable
    # 7  current number of logical volumes on this physical volume
    # 8  physical extent size in kilobytes
    # 9  total number of physical extents
    # 10 free number of physical extents
    # 11 allocated number of physical extents
    return [
        {
            'block_dev': pv_data[0],
            'group': pv_data[1],
            # Skipping "physical volume size in kilobytes" as it seems bugged
            # 'size': int(pv_data[2], base=10),
            # Skipping "internal physical volume number"
            'status': pv_data[4],
            # Skipping "physical volume (not) allocatable"
            # Skipping "current number of logical volumes..."
            # 'lv_number': int(pv_data[6], base=10),
            'extent_size': int(pv_data[7], base=10),
            'extent_nb': int(pv_data[8], base=10),
            'extent_free': int(pv_data[9], base=10),
            'extent_alloc': int(pv_data[10], base=10),
        }
        for pv_data in info_data
    ]


###############################################################################
def vgcreate(group, device):
    """Create a new LVM volume group.
    """
    return subproc.check_call(
        [
            'lvm',
            'vgcreate',
            '--autobackup', 'n',
            group,
            device,
        ]
    )


###############################################################################
def vgremove(group):
    """Destroy a LVM volume group.
    """
    return subproc.check_call(
        [
            'lvm',
            'vgremove',
            '--force',
            group,
        ]
    )


###############################################################################
def vgactivate(group):
    """Activate a LVM volume group.
    """
    return subproc.check_call(
        [
            'lvm',
            'vgchange',
            '--activate', 'y',
            group,
        ]
    )


###############################################################################
def _parse_vg_data(vg_data):
    """Parse LVM volume group data.
    """
    if len(vg_data) != 17:
        _LOGGER.critical('Invalid volume group info: %r', vg_data)
        return None

    # The values are:
    #
    # 1  volume group name
    # 2  volume group access
    # 3  volume group status
    # 4  internal volume group number
    # 5  maximum number of logical volumes
    # 6  current number of logical volumes
    # 7  open count of all logical volumes in this volume group
    # 8  maximum logical volume size
    # 9  maximum number of physical volumes
    # 10 current number of physical volumes
    # 11 actual number of physical volumes
    # 12 size of volume group in kilobytes
    # 13 physical extent size
    # 14 total number of physical extents for this volume group
    # 15 allocated number of physical extents for this volume group
    # 16 free number of physical extents for this volume group
    # 17 uuid of volume group
    #
    return {
        'name': vg_data[0],
        'access': vg_data[1],
        'status': vg_data[2],
        'number': int(vg_data[3], base=10),
        'lv_max': int(vg_data[4], base=10),
        'lv_cur': int(vg_data[5], base=10),
        'lv_open_count': int(vg_data[6], base=10),
        'max_size': int(vg_data[7], base=10),
        'pv_max': int(vg_data[8], base=10),
        'pv_cur': int(vg_data[9], base=10),
        'pv_actual': int(vg_data[10], base=10),
        'size': int(vg_data[11], base=10),
        'extent_size': int(vg_data[12], base=10),
        'extent_nb': int(vg_data[13], base=10),
        'extent_alloc': int(vg_data[14], base=10),
        'extent_free': int(vg_data[15], base=10),
        'uuid': vg_data[16],
    }


def vgsdisplay():
    """Gather LVM volume groups information.
    """
    cmd = [
        'lvm',
        'vgdisplay',
        '--colon',
    ]

    info = subproc.check_output(cmd)
    info_data = [
        line.strip().split(':')
        for line in info.strip().split('\n')
        if line
    ]

    return [
        _parse_vg_data(vg_data)
        for vg_data in info_data
    ]


def vgdisplay(group):
    """Gather a LVM volume group information.
    """
    cmd = [
        'lvm',
        'vgdisplay',
        '--colon',
        group,
    ]

    info = subproc.check_output(cmd)
    info_data = [
        line.strip().split(':')
        for line in info.strip().split('\n')
        if line
    ]
    assert len(info_data) == 1, 'Unexpected LVM output.'

    return _parse_vg_data(info_data[0])


###############################################################################
def lvcreate(volume, size_in_bytes, group):
    """Create a new LVM logical volume.
    """
    cmd = [
        'lvm',
        'lvcreate',
        '--autobackup', 'n',
        '--wipesignatures', 'y',
        '--size', '{size}B'.format(size=size_in_bytes),
        '--name', volume,
        group,
    ]

    # NOTE(boysson): lvcreate returns 5 and a message when the volume already
    #                exists.
    #
    # lvcreate --autobackup n --size 100M --name Foo  Test
    #   Logical volume "Foo" already exists in volume group "Test"

    return subproc.check_call(cmd)


###############################################################################
def lvremove(volume, group):
    """Remove a LVM logical volume.
    """
    qualified_volume = os.path.join(group, volume)
    return subproc.check_call(
        [
            'lvm',
            'lvremove',
            '--autobackup', 'n',
            '--force',
            qualified_volume,
        ]
    )


###############################################################################
def _parse_lv_data(lv_data):
    """Parse LVM logical volume data.
    """
    if len(lv_data) != 13:
        _LOGGER.critical('Invalid logical volume info: %r', lv_data)
        return None

    # The values are:
    #
    # 1  logical volume name
    # 2  volume group name
    # 3  logical volume access
    # 4  logical volume status
    # 5  internal logical volume number
    # 6  open count of logical volume
    # 7  logical volume size in sectors
    # 8  current logical extents associated to logical volume
    # 9  allocated logical extents of logical volume
    # 10 allocation policy of logical volume
    # 11 read ahead sectors of logical volume
    # 12 major device number of logical volume
    # 13 minor device number of logical volume
    #
    return {
        'block_dev': lv_data[0],
        # NOTE(boysson): What they call name above is the 'block_dev'
        'name': os.path.basename(lv_data[0]),
        'group': lv_data[1],
        # 'access': lv_data[2],
        # 'status': lv_data[3],
        # 'number': int(lv_data[4], base=10),
        'open_count': int(lv_data[5], base=10),
        # 'size_sector': int(lv_data[6], base=10),
        'extent_size': int(lv_data[7], base=10),
        'extent_alloc': int(lv_data[8], base=10),
        # 'extent_alloc_policy': int(lv_data[9], base=10),
        # 'read_ahead': int(lv_data[10], base=10),
        'dev_major': int(lv_data[11], base=10),
        'dev_minor': int(lv_data[12], base=10),
    }


def lvsdisplay(group=None):
    """Gather LVM volumes information.
    """
    cmd = [
        'lvm',
        'lvdisplay',
        '--colon',
    ]
    if group is not None:
        cmd.append(group)

    info = subproc.check_output(cmd)
    info_data = [
        line.strip().split(':')
        for line in info.strip().split('\n')
        if line
    ]

    return [
        _parse_lv_data(lv_data)
        for lv_data in info_data
    ]


def lvdisplay(volume, group):
    """Gather a LVM volume information.
    """
    cmd = [
        'lvm',
        'lvdisplay',
        '--colon',
        os.path.join(group, volume)
    ]

    info = subproc.check_output(cmd)
    info_data = [
        line.strip().split(':')
        for line in info.strip().split('\n')
        if line
    ]
    assert len(info_data) == 1, 'Unexpected LVM output.'

    return _parse_lv_data(info_data[0])


###############################################################################
__all__ = [
    'lvcreate',
    'lvdisplay',
    'lvremove',
    'lvsdisplay',
    'pvcreate',
    'vgactivate',
    'vgcreate',
    'vgdisplay',
    'vgremove',
    'vgsdisplay',
]
