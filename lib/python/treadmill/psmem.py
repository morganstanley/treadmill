"""Reports memory usage stats.

The code is based on:
https://raw.githubusercontent.com/pixelb/ps_mem/master/ps_mem.py
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import fnmatch
import io
import logging
import os
import sys
import mmap

from treadmill import sysinfo

_LOGGER = logging.getLogger(__name__)

# Pagesize in K.
_PAGESIZE = mmap.PAGESIZE // 1024

_KERNEL_VER = sysinfo.kernel_ver()


def proc_path(*args):
    """Helper function to construct /proc path.
    """
    return os.path.join('/proc', *(str(a) for a in args))


def proc_open(*args):
    """Helper function to open /proc path.
    """
    try:
        return io.open(proc_path(*args))
    except (IOError, OSError):
        val = sys.exc_info()[1]
        # kernel thread or process gone
        if val.errno == errno.ENOENT or val.errno == errno.EPERM:
            raise LookupError
        raise


def proc_readlines(*args):
    """Read lines from /proc file.
    """
    with proc_open(*args) as f:
        return f.readlines()


def proc_readline(*args):
    """Read line from /proc file.
    """
    with proc_open(*args) as f:
        return f.readline()


def proc_read(*args):
    """Read content of /proc file.
    """
    with proc_open(*args) as f:
        return f.read()


def get_thread_id(pid):
    """Read thread group id designated in /proc/<pid>/status.
    """
    return proc_readlines(pid, 'status')[2][6:-1]


def get_threads(pid):
    """Read number of threads designated in /proc/<pid>/status.
    """
    return int(proc_readlines(pid, 'status')[26][8:-1].strip())


def get_mem_stats(pid, use_pss=True):
    """Return private, shared memory given pid.

    Note: shared is always a subset of rss (trs is not always).
    """
    statm = proc_readline(pid, 'statm').split()
    rss = int(statm[1]) * _PAGESIZE

    private_lines = []
    shared_lines = []
    pss_lines = []
    have_pss = False

    if use_pss and os.path.exists(proc_path(pid, 'smaps')):
        for line in proc_readlines(pid, 'smaps'):
            if line.startswith('Shared'):
                shared_lines.append(line)
            elif line.startswith('Private'):
                private_lines.append(line)
            elif line.startswith('Pss'):
                have_pss = True
                pss_lines.append(line)

        shared = sum([int(line.split()[1]) for line in shared_lines])
        private = sum([int(line.split()[1]) for line in private_lines])

        # shared + private = rss above
        # the Rss in smaps includes video card mem etc.
        if have_pss:
            # add 0.5KiB as this avg error due to trunctation
            pss_adjust = 0.5
            pss = sum([float(line.split()[1]) + pss_adjust
                       for line in pss_lines])
            shared = pss - private
    else:
        shared = int(statm[2]) * _PAGESIZE
        private = rss - shared

    # values are in Kbytes.
    return (int(private * 1024), int(shared * 1024), have_pss)


def get_cmd_name(pid, verbose):
    """Returns truncated command line name given pid."""
    cmdline = proc_read(pid, 'cmdline').split(r'\0')
    if cmdline[-1] == '' and len(cmdline) > 1:
        cmdline = cmdline[:-1]

    path = proc_path(pid, 'exe')
    try:
        path = os.readlink(path)
        # Some symlink targets were seen to contain NULs on RHEL 5 at least
        # https://github.com/pixelb/scripts/pull/10, so take string up to NUL
        path = path.split(r'\0')[0]
    except OSError as err:
        val = sys.exc_info()[1]
        # either kernel thread or process gone
        if val.errno == errno.ENOENT or val.errno == errno.EPERM:
            raise LookupError
        _LOGGER.error('OS Error: %s', err)
        raise

    if verbose:
        return cmdline[0].replace('\x00', ' ')

    if path.endswith(' (deleted)'):
        path = path[:-10]
        if os.path.exists(path):
            path += ' [updated]'
        else:
            # The path could be have prelink stuff so try cmdline
            # which might have the full path present. This helped for:
            # /usr/libexec/notification-area-applet.#prelink#.fX7LCT (deleted)
            if os.path.exists(cmdline[0]):
                path = cmdline[0] + ' [updated]'
            else:
                path += ' [deleted]'

    exe = os.path.basename(path)
    cmd = proc_readline(pid, 'status')[6:-1]
    if exe.startswith(cmd):
        cmd = exe

    return cmd


def get_memory_usage(pids, verbose=False, exclude=None, use_pss=True):
    """Returns memory stats for list of pids, aggregated by cmd line."""
    # TODO: pylint complains about too many branches, need to refactor.
    # pylint: disable=R0912
    meminfos = []

    for pid in pids:
        thread_id = int(get_thread_id(pid))
        if not pid or thread_id != pid:
            continue

        try:
            cmd = get_cmd_name(pid, verbose)
        except LookupError:
            # kernel threads don't have exe links or
            # process gone
            continue
        except OSError:
            # operation not permitted
            continue

        if exclude:
            match = False
            for pattern in exclude:
                if fnmatch.fnmatch(cmd, pattern):
                    match = True
                    break
            if match:
                continue

        meminfo = {}
        meminfo['name'] = cmd
        meminfo['tgid'] = thread_id
        try:
            private, shared, have_pss = get_mem_stats(pid, use_pss=use_pss)
        except RuntimeError:
            continue  # process gone

        if 'shared' in meminfo:
            if have_pss:
                meminfo['shared'] += shared
            else:
                meminfo['shared'] = max(meminfo['shared'], shared)
        else:
            meminfo['shared'] = shared

        meminfo['private'] = meminfo.setdefault('private', 0) + private
        meminfo['threads'] = get_threads(pid)
        meminfo['total'] = meminfo['private'] + meminfo['shared']
        meminfos.append(meminfo)

    return meminfos
