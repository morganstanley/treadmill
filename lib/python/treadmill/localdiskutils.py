"""Common local disk utils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import re

import six

from treadmill import exc
from treadmill import fs
from treadmill import lvm
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

#: Name of the Treadmill LVM volume group
TREADMILL_VG = 'treadmill'

#: Name of the Treadmill loopback image file
TREADMILL_IMG = 'treadmill.img'

#: Minimum size for the Treadmill volume group. If we can't use this much, the
#: server node start will fail
TREADMILL_MIN_VG_SIZE = utils.size_to_bytes('100M')

#: Minimum free disk space to leave for the OS
TREADMILL_MIN_RESERVE_SIZE = utils.size_to_bytes('100M')

#: Number of loop devices to initialize
TREADMILL_LOOPDEV_NB = 8


def refresh_vg_status(group):
    """Query LVM for the current volume group status.
    """
    vg_info = lvm.vgdisplay(group=group)
    status = {
        'name': vg_info['name'],
        'extent_size': utils.size_to_bytes(
            '{kb}k'.format(kb=vg_info['extent_size'])
        ),
        'extent_free': vg_info['extent_free'],
        'extent_nb': vg_info['extent_nb'],
    }
    return status


def init_vg(group, block_dev):
    """Initialize volume group.

    :param group:
        Name of the LVM Volume Group.
    :type group:
        ``str``
    :param block_dev:
        LVM Physical Volume device backing the Volume Group
    :type block_dev:
        ``str``
    """
    # Can we see the Volume Group now that we have the block device? If
    # so, we are done.
    try:
        lvm.vgactivate(group)
        return

    except subproc.CalledProcessError:
        # The Volume group doesn't exist, more work to do
        pass

    # Create Physical Volume backend
    lvm.pvcreate(device=block_dev)
    # Create a Volume Group using the above Physical Volume
    lvm.vgcreate(group, device=block_dev)
    # Activate this Volume Group
    lvm.vgactivate(group)


def init_loopback_devices(loopdevice_numbers):
    """Create and initialize loopback devices."""
    for i in six.moves.range(0, loopdevice_numbers):
        if not os.path.exists('/dev/loop%s' % i):
            subproc.check_call(['mknod', '-m660', '/dev/loop%s' % i, 'b',
                                '7', str(i)])
            subproc.check_call(['chown', 'root.disk', '/dev/loop%s' % i])


def loop_dev_for(filename):
    """Lookup the loop device associated with a given filename.

    :param filename:
        Name of the file
    :type filename:
        ``str``
    :returns:
        Name of the loop device or None if not found
    :raises:
        subproc.CalledProcessError if the file doesn't exist
    """
    filename = os.path.realpath(filename)
    loop_dev = subproc.check_output(
        [
            'losetup',
            '-j',
            filename
        ]
    )
    loop_dev = loop_dev.strip()

    match = re.match(
        r'^(?P<loop_dev>[^:]+):.*\({fname}\)'.format(fname=filename),
        loop_dev
    )
    if match is not None:
        loop_dev = match.groupdict()['loop_dev']
    else:
        loop_dev = None

    return loop_dev


def create_image(img_name, img_location, img_size):
    """Create a sparse file of the appropriate size.
    """
    fs.mkdir_safe(img_location)
    filename = os.path.join(img_location, img_name)

    retries = 10
    while retries > 0:
        retries -= 1
        try:
            stats = os.stat(filename)
            os.unlink(filename)
            _LOGGER.info('Disk image found and unlinked: %r; stat: %r',
                         filename, stats)
        except OSError as err:
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

        available_size = sysinfo.disk_usage(img_location)
        img_size_bytes = utils.size_to_bytes(img_size)
        if img_size_bytes <= 0:
            real_img_size = available_size.free - abs(img_size_bytes)
        else:
            real_img_size = img_size_bytes

        if (real_img_size < TREADMILL_MIN_VG_SIZE or
                available_size.free <
                real_img_size + TREADMILL_MIN_RESERVE_SIZE):
            raise exc.NodeSetupError('Not enough free disk space')

        if fs.create_excl(filename, real_img_size):
            break

    if retries == 0:
        raise exc.NodeSetupError('Something is messing with '
                                 'disk image creation')


def init_block_dev(img_name, img_location, img_size='-2G'):
    """Initialize a block_dev suitable to back the Treadmill Volume Group.

    The physical volume size will be auto-size based on the available capacity
    minus the reserved size.

    :param img_name:
        Name of the file which is going to back the new volume group.
    :type img_name:
        ``str``
    :param img_location:
        Path name to the file which is going to back the new volume group.
    :type img_location:
        ``str``
    :param img_size:
        Size of the image or reserved amount of free filesystem space
        to leave to the OS if negative, in bytes or using a literal
        qualifier (e.g. "2G").
    :type size:
        ``int`` or ``str``
    """
    filename = os.path.join(img_location, img_name)

    # Initialize the OS loopback devices (needed to back the Treadmill
    # volume group by a file)
    init_loopback_devices(TREADMILL_LOOPDEV_NB)

    try:
        loop_dev = loop_dev_for(filename)

    except subproc.CalledProcessError:
        # The file doesn't exist.
        loop_dev = None

    # Assign a loop device (if not already assigned)
    if not loop_dev:
        # Create image
        if not os.path.isfile(filename):
            create_image(img_name, img_location, img_size)
        # Create the loop device
        subproc.check_call(
            [
                'losetup',
                '-f',
                filename
            ]
        )
        loop_dev = loop_dev_for(filename)

    if not loop_dev:
        raise exc.NodeSetupError('Unable to find /dev/loop device')

    _LOGGER.info('Using %r as backing for the physical volume group', loop_dev)
    return loop_dev


def setup_device_lvm(block_dev, vg_name=TREADMILL_VG):
    """Setup the LVM Volume Group based on block device"""
    activated = activate_vg(vg_name)
    if not activated:
        _LOGGER.info('Initializing Volume Group')
        init_vg(vg_name, block_dev)
    return activated


def setup_image_lvm(img_name, img_location, img_size,
                    vg_name=TREADMILL_VG):
    """Setup the LVM Volume Group based on image file"""
    activated = activate_vg(vg_name)
    if not activated:
        _LOGGER.info('Initializing Volume Group')
        block_dev = init_block_dev(
            img_name,
            img_location,
            img_size
        )
        init_vg(vg_name, block_dev)
    return activated


def cleanup_device_lvm(block_dev, vg_name=TREADMILL_VG):
    """Clean up lvm env"""
    _LOGGER.info('Destroying Volume Group')
    lvm.vgremove(vg_name)
    lvm.pvremove(block_dev)


def cleanup_image_lvm(img_name, img_location, vg_name=TREADMILL_VG):
    """Clean up lvm env"""
    _LOGGER.info('Destroying Volume Group')
    img_file = os.path.join(img_location, img_name)
    lvm.vgremove(vg_name)
    loop_device = loop_dev_for(img_file)
    if loop_device is not None:
        lvm.pvremove(loop_device)
        loopdetach(loop_device)
    if os.path.isfile(img_file):
        os.unlink(img_file)


def activate_vg(vg_name):
    """Try activating vg"""
    try:
        lvm.vgactivate(group=vg_name)
        return True
    except subproc.CalledProcessError:
        return False


def loopdetach(device):
    """Detach specified loop device"""
    return subproc.check_call(
        [
            'losetup',
            '-d',
            device,
        ]
    )
