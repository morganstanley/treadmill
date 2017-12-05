"""Configures NFS inside the container.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill.runtime.linux.image import fs as image_fs


class NFSFilesystemPlugin(image_fs.FilesystemPluginBase):
    """Mounts nfs based on container environment."""
    def __init__(self, tm_env):
        super(NFSFilesystemPlugin, self).__init__(tm_env)

    def init(self):
        """Pre mount NFS shares for private nfs namespace to a Treadmill known
        location.

        This is done to avoid NFS delays at container create time."""
        pass

    def configure(self, container_dir, app):
        pass
