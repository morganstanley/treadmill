"""Linux sysinfo(2) API wrapper module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

import ctypes
from ctypes.util import find_library


# Map the C interface

_LIBC_PATH = find_library('c')
_LIBC = ctypes.CDLL(_LIBC_PATH, use_errno=True)

if not getattr(_LIBC, 'sysinfo', None):
    raise ImportError('Unsupported libc version found: %s' % _LIBC_PATH)


class SysInfo(ctypes.Structure):
    """struct sysinfo.

       struct sysinfo {
           long uptime;             /* Seconds since boot */
           unsigned long loads[3];  /* 1, 5, and 15 minute load averages */
           unsigned long totalram;  /* Total usable main memory size */
           unsigned long freeram;   /* Available memory size */
           unsigned long sharedram; /* Amount of shared memory */
           unsigned long bufferram; /* Memory used by buffers */
           unsigned long totalswap; /* Total swap space size */
           unsigned long freeswap;  /* swap space still available */
           unsigned short procs;    /* Number of current processes */
           unsigned long totalhigh; /* Total high memory size */
           unsigned long freehigh;  /* Available high memory size */
           unsigned int mem_unit;   /* Memory unit size in bytes */
           char _f[20-2*sizeof(long)-sizeof(int)]; /* Padding for libc5 */
       };
    """
    _fields_ = [('uptime', ctypes.c_long),
                ('loads', ctypes.c_long * 3),
                ('totalrun', ctypes.c_long),
                ('freeram', ctypes.c_long),
                ('sharedram', ctypes.c_long),
                ('bufferram', ctypes.c_long),
                ('totalswap', ctypes.c_long),
                ('freeswap', ctypes.c_long),
                ('procs', ctypes.c_short),
                ('totalhigh', ctypes.c_long),
                ('freehigh', ctypes.c_long),
                ('mem_unit', ctypes.c_int),
                ('_f', ctypes.c_char * (20 -
                                        2 * ctypes.sizeof(ctypes.c_long) -
                                        ctypes.sizeof(ctypes.c_int)))]


def sysinfo():
    """Returns sysinfo, raises on error."""
    info = SysInfo()
    res = _LIBC.sysinfo(ctypes.byref(info))
    if res < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), 'sysinfo')

    return info


###############################################################################
__all__ = [
    'sysinfo',
]
