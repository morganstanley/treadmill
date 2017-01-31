"""Wrapper for unshare(2) system call."""

import logging
import os

import ctypes

from ctypes import (
    c_int,
)

from ctypes.util import find_library


_LOG = logging.getLogger(__name__)


###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if getattr(_LIBC, 'unshare', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)

# int unshare(int);
_UNSHARE_DECL = ctypes.CFUNCTYPE(c_int, c_int, use_errno=True)
_UNSHARE = _UNSHARE_DECL(('unshare', _LIBC))


def unshare(what):
    """disassociate parts of the process execution context.
    """
    retcode = _UNSHARE(what)
    if retcode != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), what)


###############################################################################
# Constants copied from bits/sched.h
#
# See man unshare(2) for more details.
#
CLONE_VM = 0x00000100
CLONE_FS = 0x00000200
CLONE_FILES = 0x00000400
CLONE_SIGHAND = 0x00000800
CLONE_PTRACE = 0x00002000
CLONE_VFORK = 0x00004000
CLONE_PARENT = 0x00008000
CLONE_THREAD = 0x00010000
CLONE_NEWNS = 0x00020000
CLONE_SYSVSEM = 0x00040000
CLONE_SETTLS = 0x00080000
CLONE_PARENT_SETTID = 0x00100000
CLONE_CHILD_CLEARTID = 0x00200000
CLONE_DETACHED = 0x00400000
CLONE_UNTRACED = 0x00800000
CLONE_CHILD_SETTID = 0x01000000
CLONE_NEWUTS = 0x04000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
CLONE_IO = 0x80000000
