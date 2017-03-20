"""Configures NFS inside the container."""


def init(rootdir):
    """Pre mount NFS shares for private nfs namespace to a Treadmill known
    location.

    This is done to avoid NFS delays at container create time."""
    del rootdir


def configure(approot, newroot, app):
    """Mounts nfs based on container environment."""
    del approot
    del newroot
    del app
