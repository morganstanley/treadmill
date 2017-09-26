"""Wrapper for eventfd(2) system call.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import ctypes
from ctypes import (
    c_int,
    c_uint,
)
from ctypes.util import find_library

import enum

_LOGGER = logging.getLogger(__name__)


###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if getattr(_LIBC, 'eventfd', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)

# int eventfd(unsigned int initval, int flags);
_EVENTFD_DECL = ctypes.CFUNCTYPE(c_int, c_uint, c_int, use_errno=True)
_EVENTFD = _EVENTFD_DECL(('eventfd', _LIBC))


def eventfd(initval, flags):
    """create a file descriptor for event notification.
    """
    if initval < 0 or initval > (2**64 - 1):
        raise ValueError('Invalid initval: %r' % initval)

    fileno = _EVENTFD(initval, flags)
    if fileno < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno),
                      'eventfd(%r, %r)' % (initval, flags))
    return fileno


###############################################################################
# Constants copied from sys/eventfd.h
#
# See man eventfd(2) for more details.
#
class EFDFlags(enum.IntEnum):
    """Flags supported by EventFD.
    """

    #: Provice semaphore-like semantics for reads from the new file descriptor.
    SEMAPHORE = 1

    #: Set the O_NONBLOCK file status flag on the new open file description.
    #: Using this flag saves extra calls to fcntl(2) to achieve the same
    #: result.
    NONBLOCK = 0o4000

    #: Set the close-on-exec (FD_CLOEXEC) flag on the new file descriptor.  See
    #: the description of the O_CLOEXEC flag in open(2) for reasons why this
    #: may be useful.
    CLOEXEC = 0o2000000

    @classmethod
    def parse(cls, flags):
        """Parse EventFD flags into list of flags.
        """
        masks = []
        remain_flags = flags
        # pylint - Non-iterable value cls is used in an iterating context
        for flag in cls:  # pylint: disable=E1133
            if flags & flag.value:
                remain_flags ^= flag.value
                masks.append(flag)

        if remain_flags:
            masks.append(remain_flags)

        return masks


#: Provice semaphore-like semantics for reads from the new file descriptor.
#: (since Linux 2.6.30)
EFD_SEMAPHORE = EFDFlags.SEMAPHORE

#: Set the O_NONBLOCK file status flag on the new open file description.  Using
#: this flag saves extra calls to fcntl(2) to achieve the same result.
#: (since Linux 2.6.27)
EFD_NONBLOCK = EFDFlags.NONBLOCK

#: Set the close-on-exec (FD_CLOEXEC) flag on the new file descriptor.  See
#: the description of the O_CLOEXEC flag in open(2) for reasons why this may be
#: useful.
#: (since Linux 2.6.27)
EFD_CLOEXEC = EFDFlags.CLOEXEC


###############################################################################
__all__ = [
    'EFD_SEMAPHORE',
    'EFD_NONBLOCK',
    'EFD_CLOEXEC',
    'eventfd',
]
