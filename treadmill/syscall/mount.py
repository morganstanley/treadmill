"""Linux mount(2) API wrapper module
"""

import logging
import os
import ctypes

from ctypes import (
    c_int,
    c_char_p,
    c_ulong,
    c_void_p,
)

from ctypes.util import find_library


_LOG = logging.getLogger(__name__)

###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if (not getattr(_LIBC, 'mount', None) or
        not getattr(_LIBC, 'umount', None) or
        not getattr(_LIBC, 'umount2', None)):
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)


# int mount(const char *source, const char *target,
#           const char *filesystemtype, unsigned long mountflags,
#           const void *data);
_MOUNT_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_char_p,  # source
    c_char_p,  # target
    c_char_p,  # filesystem type
    c_ulong,   # mount flags
    c_void_p,  # data
    use_errno=True
)
_MOUNT = _MOUNT_DECL(('mount', _LIBC))


def mount(source, target, fs_type, mnt_flags=()):
    """Mount ``source`` on ``target`` using filesystem type ``fs_type`` and
    mount flags ``mnt_flags``.

    NOTE: Mount data argument is not supported.
    """
    res = _MOUNT(source, target, fs_type, mnt_flags, 0)
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(
            errno, os.strerror(errno),
            'mount(%r, %r, %r, %r)' % (source, target, fs_type, mnt_flags)
        )

    return res


# int umount(const char *target);
_UMOUNT_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_char_p,  # target
    use_errno=True
)
_UMOUNT = _UMOUNT_DECL(('umount', _LIBC))

# int umount2(const char *target, int flags);
_UMOUNT2_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_char_p,  # target
    c_int,     # flags
    use_errno=True
)
_UMOUNT2 = _UMOUNT2_DECL(('umount2', _LIBC))


def unmount(target, flags=None):
    """Unmount ``target``."""
    res = 0
    if flags is None:
        res = _UMOUNT(target)
        if res < 0:
            errno = ctypes.get_errno()
            raise OSError(
                errno, os.strerror(errno),
                'umount(%r)' % (target, )
            )

    else:
        res = _UMOUNT2(target, flags)
        if res < 0:
            errno = ctypes.get_errno()
            raise OSError(
                errno, os.strerror(errno),
                'umount2(%r, %r)' % (target, flags)
            )

    return res


###############################################################################
# NOTE(boysson): below values taken from mount kernel interface sys/mount.h

# Mount flags

#: Mount read-only.
MS_RDONLY = 1

#: Ignore suid and sgid bits.
MS_NOSUID = 2

#: Disallow access to device special files.
MS_NODEV = 4

#: Disallow program execution.
MS_NOEXEC = 8

#: Writes are synced at once.
MS_SYNCHRONOUS = 16

#: Alter flags of a mounted FS.
MS_REMOUNT = 32

#: Allow mandatory locks on an FS.
MS_MANDLOCK = 64

#: Directory modifications are synchronous.
MS_DIRSYNC = 128

#: Do not update access times.
MS_NOATIME = 1024

#: Do not update directory access times.
MS_NODIRATIME = 2048

#: Bind a mount point to a different place .
MS_BIND = 4096

#: Move a mount point to a different place .
MS_MOVE = 8192

#: Recursively apply the UNBINDABLE, PRIVATE, SLAVE, or SHARED flags.
MS_REC = 16384

# See https://www.kernel.org/doc/Documentation/filesystems/sharedsubtree.txt

#: unbindable mount
MS_UNBINDABLE = 1 << 17

#: private mount
MS_PRIVATE = 1 << 18

#: slave mount
MS_SLAVE = 1 << 19

#: shared mount
MS_SHARED = 1 << 20

# Umount2 operations flags

#: Force unmounting
MNT_FORCE = 1

#: Just detach from the tree
MNT_DETACH = 2

#: Mark for expiry
MNT_EXPIRE = 4
