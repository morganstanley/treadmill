"""Wrapper for unshare(2) system call.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import ctypes
from ctypes import (
    c_int, c_char_p,
)
from ctypes.util import find_library

_LOGGER = logging.getLogger(__name__)


###############################################################################
# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if getattr(_LIBC, 'chroot', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)

# int unshare(int);
_CHROOT_DECL = ctypes.CFUNCTYPE(c_int, c_char_p, use_errno=True)
_CHROOT = _CHROOT_DECL(('chroot', _LIBC))


def chroot(path):
    """disassociate parts of the process execution context.
    """
    if path is not None:
        path = path.encode()

    retcode = _CHROOT(path)
    if retcode != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), path)

    return retcode


__all__ = [
    'chroot',
]
