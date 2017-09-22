"""Manage container filesystem layout.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import stat

# pylint: disable=E0611
from treadmill import fs

from treadmill.runtime.linux.image import fs as image_fs


class LocalFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Configure layout in chroot."""
    def __init__(self, tm_env):
        super(LocalFilesystemPlugin, self).__init__(tm_env)

    def init(self):
        pass

    def configure(self, container_dir, app):
        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)
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
            os.chmod(newroot_norm + directory, 0o777 | stat.S_ISVTX)
