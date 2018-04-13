"""Wrapper for signalfd(2) system call.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os

import ctypes
from ctypes import (
    c_int,
    c_void_p,
    c_uint32,
    c_uint64,
    c_uint8,
    c_int32,
)
from ctypes.util import find_library

import enum

from ._sigsetops import (
    SigSet,
    sigaddset,
    sigfillset,
)

_LOGGER = logging.getLogger(__name__)


###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if getattr(_LIBC, 'signalfd', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)

###############################################################################
# int signalfd(int fd, const sigset_t *mask, int flags);
_SIGNALFD_DECL = ctypes.CFUNCTYPE(c_int, c_int, c_void_p, c_int,
                                  use_errno=True)
_SIGNALFD = _SIGNALFD_DECL(('signalfd', _LIBC))


def signalfd(sigset, flags=0, prev_fd=-1):
    """create/update a signal file descriptor.
    """
    if isinstance(sigset, SigSet):
        new_set = sigset

    elif sigset == 'all':
        new_set = SigSet()
        sigfillset(new_set)

    else:
        new_set = SigSet()
        for signum in sigset:
            sigaddset(new_set, signum)

    new_set_p = ctypes.pointer(new_set)
    fileno = _SIGNALFD(prev_fd, new_set_p, flags)
    if fileno < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err),
                      'signalfd(%r, %r, %r)' % (prev_fd, new_set, flags))
    return fileno


###############################################################################
# Constants copied from sys/signalfd.h
#
# See man signalfd(2) for more details.
#
class SFDFlags(enum.IntEnum):
    """Flags supported by SignalFD.
    """

    #: Set the O_NONBLOCK file status flag on the new open file description.
    #: Using this flag saves extra calls to fcntl(2) to achieve the same
    #: result.
    NONBLOCK = 0o4000

    #: Set the close-on-exec (FD_CLOEXEC) flag on the new file descriptor.  See
    #: the description of the O_CLOEXEC flag in open(2) for reasons why this
    #: may be useful.
    CLOEXEC = 0o2000000


#: Set the O_NONBLOCK file status flag on the new open file description.  Using
#: this flag saves extra calls to fcntl(2) to achieve the same result.
#: (since Linux 2.6.27)
SFD_NONBLOCK = SFDFlags.NONBLOCK

#: Set the close-on-exec (FD_CLOEXEC) flag on the new file descriptor.  See the
#: description of the O_CLOEXEC flag in open(2) for reasons why this may be
#: useful.
#: (since Linux 2.6.27)
SFD_CLOEXEC = SFDFlags.CLOEXEC


###############################################################################
# The signalfd_siginfo structure
#
class SFDSigInfo(ctypes.Structure):
    """The signalfd_siginfo structure.

    The format of the signalfd_siginfo structure(s) returned by read(2)s from a
    signalfd file descriptor is as follows:

        struct signalfd_siginfo {
            uint32_t ssi_signo;   /* Signal number */
            int32_t  ssi_errno;   /* Error number (unused) */
            int32_t  ssi_code;    /* Signal code */
            uint32_t ssi_pid;     /* PID of sender */
            uint32_t ssi_uid;     /* Real UID of sender */
            int32_t  ssi_fd;      /* File descriptor (SIGIO) */
            uint32_t ssi_tid;     /* Kernel timer ID (POSIX timers)
            uint32_t ssi_band;    /* Band event (SIGIO) */
            uint32_t ssi_overrun; /* POSIX timer overrun count */
            uint32_t ssi_trapno;  /* Trap number that caused signal */
            int32_t  ssi_status;  /* Exit status or signal (SIGCHLD) */
            int32_t  ssi_int;     /* Integer sent by sigqueue(2) */
            uint64_t ssi_ptr;     /* Pointer sent by sigqueue(2) */
            uint64_t ssi_utime;   /* User CPU time consumed (SIGCHLD) */
            uint64_t ssi_stime;   /* System CPU time consumed (SIGCHLD) */
            uint64_t ssi_addr;    /* Address that generated signal
                                     (for hardware-generated signals) */
            uint8_t  pad[X];      /* Pad size to 128 bytes (allow for
                                      additional fields in the future) */
        };

    """
    # pylint: disable=bad-whitespace
    _FIELDS = [
        ('ssi_signo', c_uint32),    #: Signal number
        ('ssi_errno', c_int32),     #: Error number (unused)
        ('ssi_code', c_int32),      #: Signal code
        ('ssi_pid', c_uint32),      #: PID of sender
        ('ssi_uid', c_uint32),      #: Real UID of sender
        ('ssi_fd', c_int32),        #: File descriptor (SIGIO)
        ('ssi_tid', c_uint32),      #: Kernel timer ID (POSIX timers)
        ('ssi_band', c_uint32),     #: Band event (SIGIO)
        ('ssi_overrun', c_uint32),  #: POSIX timer overrun count
        ('ssi_trapno', c_uint32),   #: Trap number that caused signal
        ('ssi_status', c_int32),    #: Exit status or signal (SIGCHLD)
        ('ssi_int', c_int32),       #: Integer sent by sigqueue(2)
        ('ssi_ptr', c_uint64),      #: Pointer sent by sigqueue(2)
        ('ssi_utime', c_uint64),    #: User CPU time consumed (SIGCHLD)
        ('ssi_stime', c_uint64),    #: System CPU time consumed (SIGCHLD)
        ('ssi_addr', c_uint64),     #: Address that generated signal
    ]
    __PADWORDS = 128 - sum([ctypes.sizeof(field[1]) for
                            field in _FIELDS])

    _fields_ = _FIELDS + [
        ('_pad', c_uint8 * __PADWORDS),  # Pad size to 128 bytes (allow for
                                         # additional fields in the future)
    ]


def signalfd_read(sfd):
    """Read signalfd_siginfo data from a signalfd filedescriptor.
    """
    try:
        data = os.read(sfd, ctypes.sizeof(SFDSigInfo))

    except OSError as err:
        # Ignore signal interruptions
        if err.errno != errno.EINTR:
            raise
        return None

    return SFDSigInfo.from_buffer_copy(data)


###############################################################################
__all__ = [
    'SFD_NONBLOCK',
    'SFD_CLOEXEC',
    'signalfd',
    'signalfd_read',
]
