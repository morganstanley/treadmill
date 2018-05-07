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

if getattr(_LIBC, 'pivot_root', None) is None:
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)

# int unshare(int);
_PIVOT_ROOT_DECL = ctypes.CFUNCTYPE(c_int, c_char_p, c_char_p, use_errno=True)
_PIVOT_ROOT = _PIVOT_ROOT_DECL(('pivot_root', _LIBC))


def pivot_root(new_root, put_old):
    """disassociate parts of the process execution context.
    """
    if new_root is not None:
        new_root = new_root.encode()

    if put_old is not None:
        put_old = put_old.encode()

    retcode = _PIVOT_ROOT(new_root, put_old)
    if retcode != 0:
        errno = ctypes.get_errno()
        msg = '{} => {}'.format(put_old, new_root)
        raise OSError(errno, os.strerror(errno), msg)

    return retcode


__all__ = [
    'pivot_root',
]
