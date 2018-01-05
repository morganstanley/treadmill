"""Configures NFS inside the container.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging

from treadmill import fs
from treadmill.fs import linux as fs_linux
from treadmill.runtime.linux.image import fs as image_fs

_LOGGER = logging.getLogger(__name__)

# List of all nfs environments
_NFS_ENVIRONMENTS = ['prod', 'qa', 'uat', 'dev']


class NFSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Mounts nfs based on container environment."""

    def init(self):
        """Pre mount NFS shares for private nfs namespace to a Treadmill known
        location.

        This is done to avoid NFS delays at container create time."""
        mounts_dir = os.path.join(self.tm_env.root, 'mnt', 'nfs')
        fs.mkdir_safe(mounts_dir, mode=0o700)  # NFS dirs need to be private
        for env in _NFS_ENVIRONMENTS:
            # FIXME: This is hardcoded location from a Aquilon TM feature.
            nfs_mount = '/.v.private/' + env
            if os.path.exists(nfs_mount):
                fs_linux.mount_bind(
                    mounts_dir, os.path.join(os.sep, env),
                    source=nfs_mount,
                    recursive=True, read_only=False
                )
                _LOGGER.info('%s: ok', nfs_mount)
            else:
                _LOGGER.warning('%s: not found', nfs_mount)

    def configure(self, container_dir, app):
        # Mount /tmp_ns based on container environment.
        # If private_ns not available fallback to /tmp_ns.
        root_dir = os.path.join(container_dir, 'root')
        newroot_norm = fs.norm_safe(root_dir)
        nfs_mount = os.path.join(self.tm_env.root, 'mnt', 'nfs',
                                 app.environment)
        # FIXME: This is hardcoded location + trying to autoguess presence
        #        of the Aquilon TM NFS feature.
        if not os.path.exists(nfs_mount):
            nfs_mount = '/tmp_ns'

        _LOGGER.info('Binding /v to %s', nfs_mount)
        fs_linux.mount_bind(
            newroot_norm, os.path.join(os.sep, 'v'),
            source=nfs_mount,
            recursive=True, read_only=False
        )
