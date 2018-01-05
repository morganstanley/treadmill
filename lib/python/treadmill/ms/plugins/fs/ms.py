"""Manage MS specific filesystem layout.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pwd
import stat

from treadmill import fs
from treadmill.fs import linux as fs_linux
from treadmill.runtime.linux.image import fs as image_fs

_LOGGER = logging.getLogger(__name__)


class MinimalMSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Configure layout in chroot.
    """

    def init(self):
        pass

    def configure(self, container_dir, app):
        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)

        emptydirs = [
            '/common',
            '/opt/treadmill',  # FIXME: This shouldn't be here.
            '/var/account',
            '/var/db',
            '/var/empty',
            '/var/hostlinks',
            '/var/mqm',
            '/var/spool/keytabs',
            '/var/spool/tickets',
            '/var/spool/tokens',
            '/var/tmp/cores',
        ]

        stickydirs = [
            '/var/hostlinks',
            '/var/spool/keytabs',
            '/var/spool/tickets',
            '/var/spool/tokens',
            '/var/tmp/cores',
        ]

        mounts = [
            '/common',
            '/mnt',
            '/opt/treadmill',  # FIXME: This shouldn't be here.
            '/opt/rh',
            '/var/db',
            '/var/mqm',
        ]

        for directory in emptydirs:
            fs.mkdir_safe(newroot_norm + directory)

        for directory in stickydirs:
            os.chmod(newroot_norm + directory, 0o777 | stat.S_ISVTX)

        for mount in mounts:
            if os.path.exists(mount):
                fs_linux.mount_bind(
                    newroot_norm, mount,
                    recursive=False, read_only=False
                )

        # Mount .../tickets .../keytabs on tempfs, so that they will be cleaned
        # up when the container exits.
        #
        for tmpfsdir in ['/var/spool/tickets',
                         '/var/spool/keytabs',
                         '/var/spool/tokens']:
            fs_linux.mount_tmpfs(newroot_norm, tmpfsdir)

        # TODO: Deprecate this.
        # Set the container's proid as the owner of '/home'.
        pwnam = pwd.getpwnam(app.proid)
        os.chown(os.path.join(newroot_norm, 'home'),
                 pwnam.pw_uid, pwnam.pw_gid)


class MSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Configure layout in chroot."""

    def init(self):
        pass

    def configure(self, container_dir, app):
        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)
        mounts = [
            '/a',
            '/d'
        ]

        emptydirs = [
            '/u',
        ]

        stickydirs = [
            '/u',
        ]

        for mount in mounts:
            if os.path.exists(mount):
                fs_linux.mount_bind(
                    newroot_norm, mount,
                    recursive=True, read_only=False
                )

        for directory in emptydirs:
            fs.mkdir_safe(newroot_norm + directory)

        for directory in stickydirs:
            os.chmod(newroot_norm + directory, 0o777 | stat.S_ISVTX)

        MinimalMSFilesystemPlugin(self.tm_env).configure(container_dir, app)
