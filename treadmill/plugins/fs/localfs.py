"""Manage container filesystem layout."""

import os
import stat

# pylint: disable=E0611
from treadmill import fs


def init(_rootdir):
    """Init filesystem layout."""
    pass


def configure(_approot, newroot, _app):
    """Configure layout in chroot."""
    newroot_norm = fs.norm_safe(newroot)
    mounts = [
    ]

    emptydirs = [
        '/u',
        '/var/account',
        '/var/empty',
        '/var/lock',
        '/var/log',
        '/var/run',
    ]

    stickydirs = [
        '/opt',
    ]

    for mount in mounts:
        if os.path.exists(mount):
            fs.mount_bind(newroot_norm, mount)

    for directory in emptydirs:
        fs.mkdir_safe(newroot_norm + directory)

    for directory in stickydirs:
        os.chmod(newroot_norm + directory, 777 | stat.S_ISVTX)
