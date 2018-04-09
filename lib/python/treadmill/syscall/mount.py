"""Linux mount(2) API wrapper module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import logging
import operator
import os

import ctypes
from ctypes import (
    c_int,
    c_char_p,
    c_ulong,
    c_void_p,
)
from ctypes.util import find_library

import enum
import six

from treadmill import utils

_LOGGER = logging.getLogger(__name__)

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


def _mount(source, target, fs_type, mnt_flags, data):
    res = _MOUNT(source, target, fs_type, mnt_flags, data)
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(
            errno, os.strerror(errno),
            'mount(%r, %r, %r, 0x%x, %r)' % (
                source,
                target,
                fs_type,
                mnt_flags,
                data
            )
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


def _umount(target):
    """Umount ``target``.
    """
    res = _UMOUNT(target)
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(
            errno, os.strerror(errno),
            'umount(%r)' % (target, )
        )


def _umount2(target, flags=None):
    res = _UMOUNT2(target, flags)
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(
            errno, os.strerror(errno),
            'umount2(%r, %r)' % (target, flags)
        )


###############################################################################
# NOTE: below values taken from mount kernel interface sys/mount.h

class MSFlags(enum.IntEnum):
    """All mount flags.
    """
    #: MS_MGC_VAL is a flag marker, needs to be included in all calls.
    MGC_VAL = 0xC0ED0000

    #: Mount read-only.
    RDONLY = 0x000001
    #: Ignore suid and sgid bits.
    NOSUID = 0x000002
    #: Disallow access to device special files.
    NODEV = 0x000004
    #: Disallow program execution.
    NOEXEC = 0x000008
    #: Writes are synced at once.
    SYNCHRONOUS = 0x000010
    #: Alter flags of a mounted FS.
    REMOUNT = 0x000020
    #: Allow mandatory locks on an FS.
    MANDLOCK = 0x000040
    #: Directory modifications are synchronous.
    DIRSYNC = 0x000080
    #: Update atime relative to mtime/ctime
    RELATIME = 0x200000
    #: Do not update access times.
    NOATIME = 0x000400
    #: Do not update directory access times.
    NODIRATIME = 0x000800
    #: Bind a mount point to a different place .
    BIND = 0x001000
    #: Move a mount point to a different place .
    MOVE = 0x002000
    #: Recursively apply the UNBINDABLE, PRIVATE, SLAVE, or SHARED flags.
    REC = 0x004000

    # See https://www.kernel.org/doc/Documentation/filesystems/
    #                                                       sharedsubtree.txt
    #: unbindable mount
    UNBINDABLE = 0x020000
    #: private mount
    PRIVATE = 0x040000
    #: slave mount
    SLAVE = 0x080000
    #: shared mount
    SHARED = 0x100000


#: Mount flag marker.
MS_MGC_VAL = MSFlags.MGC_VAL

#: Mount read-only.
MS_RDONLY = MSFlags.RDONLY
#: Ignore suid and sgid bits.
MS_NOSUID = MSFlags.NOSUID
#: Disallow access to device special files.
MS_NODEV = MSFlags.NODEV
#: Disallow program execution.
MS_NOEXEC = MSFlags.NOEXEC
#: Writes are synced at once.
MS_SYNCHRONOUS = MSFlags.SYNCHRONOUS
#: Alter flags of a mounted FS.
MS_REMOUNT = MSFlags.REMOUNT
#: Allow mandatory locks on an FS.
MS_MANDLOCK = MSFlags.MANDLOCK
#: Directory modifications are synchronous.
MS_DIRSYNC = MSFlags.DIRSYNC
#: Update atime relative to mtime/ctime
MS_RELATIME = MSFlags.RELATIME
#: Do not update access times.
MS_NOATIME = MSFlags.NOATIME
#: Do not update directory access times.
MS_NODIRATIME = MSFlags.NODIRATIME
#: Bind a mount point to a different place .
MS_BIND = MSFlags.BIND
#: Move a mount point to a different place .
MS_MOVE = MSFlags.MOVE
#: Recursively apply the UNBINDABLE, PRIVATE, SLAVE, or SHARED flags.
MS_REC = MSFlags.REC

# See https://www.kernel.org/doc/Documentation/filesystems/sharedsubtree.txt
#: unbindable mount
MS_UNBINDABLE = MSFlags.UNBINDABLE
#: private mount
MS_PRIVATE = MSFlags.PRIVATE
#: slave mount
MS_SLAVE = MSFlags.SLAVE
#: shared mount
MS_SHARED = MSFlags.SHARED


class MNTFlags(enum.IntEnum):
    """All umount2 operations flags.
    """
    #: Force unmounting
    FORCE = 0x1
    #: Just detach from the tree
    DETACH = 0x2
    #: Mark for expiry
    EXPIRE = 0x4


#: Force unmounting
MNT_FORCE = MNTFlags.FORCE
#: Just detach from the tree
MNT_DETACH = MNTFlags.DETACH
#: Mark for expiry
MNT_EXPIRE = MNTFlags.EXPIRE


###############################################################################
# Main mount/umount functions

def mount(source, target, fs_type, *mnt_opts_args,
          mnt_flags=(), **mnt_opts_kwargs):
    """Mount ``source`` on ``target`` using filesystem type ``fs_type`` and
    mount flags ``mnt_flags``.

    NOTE: Mount data argument is not supported.

    :params `str` source:
        What to mount
    :params `str` target:
        Where to mount it
    """
    if source is not None:
        source = source.encode()
    if target is not None:
        target = target.encode()
    else:
        target = source
    if fs_type is not None:
        fs_type = fs_type.encode()

    # Fix up mount flags
    mnt_flags = utils.get_iterable(mnt_flags)
    flags = int(
        six.moves.reduce(
            operator.or_, mnt_flags, MS_MGC_VAL
        )
    )
    # Fix up mount options
    options = ','.join(
        itertools.chain(
            mnt_opts_args,
            (
                '%s=%s' % (key, value)
                for (key, value) in six.iteritems(mnt_opts_kwargs)
            )
        )
    )
    if options:
        options = options.encode()
    else:
        options = None

    _LOGGER.debug('mount(%r, %r, %r, %r, %r)',
                  source, target, fs_type,
                  utils.parse_mask(flags, MSFlags), options)

    return _mount(source, target, fs_type, flags, options)


def unmount(target, mnt_flags=()):
    """Umount ``target``.
    """
    target = target.encode()

    mnt_flags = utils.get_iterable(mnt_flags)
    mnt_flags = six.moves.reduce(
        operator.or_, mnt_flags, 0
    )

    _LOGGER.debug('umount(%r, %r)',
                  target, utils.parse_mask(mnt_flags, MNTFlags))

    if not mnt_flags:
        return _umount(target)

    else:
        return _umount2(target, mnt_flags)


###############################################################################

__all__ = [
    'MNT_DETACH',
    'MNT_EXPIRE',
    'MNT_FORCE',
    'MS_BIND',
    'MS_DIRSYNC',
    'MS_MANDLOCK',
    'MS_MGC_VAL',
    'MS_MOVE',
    'MS_NOATIME',
    'MS_NODEV',
    'MS_NODIRATIME',
    'MS_NOEXEC',
    'MS_NOSUID',
    'MS_PRIVATE',
    'MS_RDONLY',
    'MS_REC',
    'MS_REMOUNT',
    'MS_SHARED',
    'MS_SLAVE',
    'MS_SYNCHRONOUS',
    'MS_UNBINDABLE',
    'mount',
    'unmount',
]
