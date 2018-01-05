"""Wrapper for sigprocmask(2) operations.
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
    c_void_p,
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

if getattr(_LIBC, 'sigprocmask', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)


# int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);
_SIGPROCMASK_DECL = ctypes.CFUNCTYPE(c_int, c_int, c_void_p, c_void_p,
                                     use_errno=True)
_SIGPROCMASK = _SIGPROCMASK_DECL(('sigprocmask', _LIBC))


def sigprocmask(how, sigset, save_mask=True):
    """Examine and change blocked signals.
    """
    how = SigProcMaskHow(how)

    if isinstance(sigset, SigSet):
        new_set = sigset

    elif sigset == 'all':
        new_set = SigSet()
        sigfillset(new_set)

    else:
        new_set = SigSet()
        for signum in sigset:
            sigaddset(new_set, signum)

    if save_mask:
        old_set = SigSet()
    else:
        old_set = 0

    new_set_p = ctypes.pointer(new_set)
    old_set_p = ctypes.pointer(old_set)
    res = _SIGPROCMASK(how, new_set_p, old_set_p)
    if res < 0:
        err = ctypes.get_errno()
        raise OSError(
            err, os.strerror(err),
            'sigprocmask(%r, %r, %r)' % (how, new_set, old_set)
        )

    return old_set


###############################################################################
# Constants copied from bits/sigaction.h
#
# See man sigprocmask(2) for more details.
#
# /* Values for the HOW argument to `sigprocmask'.  */
# #define SIG_BLOCK     0   /* Block signals.  */
# #define SIG_UNBLOCK   1   /* Unblock signals.  */
# #define SIG_SETMASK   2   /* Set the set of blocked signals.  */
#
class SigProcMaskHow(enum.IntEnum):
    """How option supported by sigprocmask.
    """
    SIG_BLOCK = 0
    SIG_UNBLOCK = 1
    SIG_SETMASK = 2


#: Block signals.
SIG_BLOCK = SigProcMaskHow.SIG_BLOCK
#: Unblock signals.
SIG_UNBLOCK = SigProcMaskHow.SIG_UNBLOCK
#: Set the set of blocked signals.
SIG_SETMASK = SigProcMaskHow.SIG_SETMASK


###############################################################################
__all__ = [
    'SIG_BLOCK',
    'SIG_UNBLOCK',
    'SIG_SETMASK',
    'sigprocmask',
]
