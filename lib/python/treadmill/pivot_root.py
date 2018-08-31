"""pivot_root way to mount container
"""

import logging
import os

from treadmill import fs
from treadmill.syscall import pivot_root as proot
from treadmill.fs import linux as fs_linux

_LOGGER = logging.getLogger(__name__)

# we need to mount move /sys/xxxx
MOVE_MOUNTS = [
    'proc',
]
PIVOT_PATH = '.old-pivot'


def _umount_with_detach(entry_path):
    """umount the path,
    if failed with device busy, we detach (lazy umount) it
    """
    try:
        fs_linux.umount_filesystem(entry_path)
    except OSError as err:
        _LOGGER.warning('Failed to umount %s: %s',
                        entry_path, err)
        # 16 means device busy
        if err.errno == 16:
            try:
                fs_linux.umount_filesystem(entry_path, lazy=True)
            except OSError as err:
                _LOGGER.warning('Failed to lazy umount %s: %s',
                                entry_path, err)


def make_root(root_dir):
    """create container root by calling pivot_root
    """
    newroot_norm = fs.norm_safe(root_dir)
    old_pivot = os.path.join(newroot_norm, PIVOT_PATH)
    fs.mkdir_safe(old_pivot)

    proot.pivot_root(newroot_norm, old_pivot)
    # return list of mount to be umounted from down to top
    to_umount = move_mounts(os.path.sep + PIVOT_PATH)

    # umount entries from down to top
    for mount_entry in to_umount:
        _umount_with_detach(mount_entry.target)


def _move_mount(original_root, mount_entry):
    """mount move a single entry from original_root to new root
    """
    target = mount_entry.target[len(original_root):]
    _LOGGER.info('Mount move %r => %s', mount_entry, target)

    try:
        fs_linux.mount_move(target, mount_entry.target)
    except FileNotFoundError as err:
        _LOGGER.warning('missing mountpoint %r: %s',
                        mount_entry.target, err)


def move_mounts(original_root):
    """Move mounts from pivot_root original root to new root
    """

    _LOGGER.info('Moving all mounts in %r', MOVE_MOUNTS)
    # we may have mutiple /proc mounts, we mount the lowest in container
    full_path_move_mounts = [
        os.path.join(original_root, mount)
        for mount in MOVE_MOUNTS
    ]

    moved = {}

    mountinfo = os.path.join(
        original_root, 'proc', 'self', 'mountinfo'
    )
    sorted_mounts = fs_linux.generate_sorted_mounts(mountinfo)
    to_umount = []

    for mount_entry in sorted_mounts:
        # if not starting with original_root, the mount is added by us before
        if not mount_entry.target.startswith(original_root):
            continue

        if mount_entry.target in full_path_move_mounts:
            if mount_entry.target in moved:
                to_umount.append(mount_entry)
            else:
                _move_mount(original_root, mount_entry)
                moved[mount_entry.target] = mount_entry
        else:
            # we remove all other entries not matching move mounts
            to_umount.append(mount_entry)

    return to_umount
