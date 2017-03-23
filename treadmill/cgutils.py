"""Misc cgroup utility functions."""


import errno
import signal
import os

import glob
import logging

from . import cgroups
from . import sysinfo

from .exc import TreadmillError
from .syscall import eventfd


_LOGGER = logging.getLogger(__name__)
NANOSECS_PER_SEC = 10**9


class TreadmillCgroupError(TreadmillError):
    """Treadmill Cgroup operation error."""
    pass


def set_memory_hardlimit(cgrp, limit):
    """Set the cgroup hard-limits to the desired value.

    The logic here is complicated since the ordering of operations depends on
    weither we are lowering or raising the value.
    """
    def _lower_memory_hardlimit(cgrp, limit):
        """Lower the cgroup memory hardlimit."""
        cgroups.set_value('memory', cgrp,
                          'memory.limit_in_bytes', limit)
        cgroups.set_value('memory', cgrp,
                          'memory.memsw.limit_in_bytes', limit)

    def _raise_memory_hardlimit(cgrp, limit):
        """Raise the cgroup memory hardlimit."""
        cgroups.set_value('memory', cgrp,
                          'memory.memsw.limit_in_bytes', limit)
        cgroups.set_value('memory', cgrp,
                          'memory.limit_in_bytes', limit)

    memory_hardlimit_funs = [_lower_memory_hardlimit, _raise_memory_hardlimit]
    while memory_hardlimit_funs:
        try:
            memory_hardlimit_fun = memory_hardlimit_funs.pop(0)
            memory_hardlimit_fun(cgrp, limit)
            break

        except IOError as err:
            if err.errno == errno.EBUSY:
                # Resource busy, this means the cgroup is already using more
                # then the limit we are trying to set.
                raise TreadmillCgroupError('Unable to set hard limit to %d. '
                                           'Cgroup %r memory over limit.' %
                                           (limit, cgrp))

            elif err.errno == errno.EINVAL:
                # This means we did the hard limit operation in the wrong
                # order. If we have a different ordering to try, go ahead.
                if memory_hardlimit_funs:
                    continue

            # For any other case, raise the exception
            raise


def create_treadmill_cgroups(system_cpu_shares,
                             treadmill_cpu_shares,
                             treadmill_core_cpu_shares,
                             treadmill_apps_cpu_shares,
                             treadmill_mem,
                             treadmill_core_mem):
    """This is the core cgroup setup. Should be applied to a cleaned env."""

    cgroups.create('cpu', 'system')
    cgroups.create('cpu', 'treadmill')
    cgroups.create('cpu', 'treadmill/core')
    cgroups.create('cpu', 'treadmill/apps')

    cgroups.set_value('cpu', 'treadmill',
                      'cpu.shares', treadmill_cpu_shares)
    cgroups.set_value('cpu', 'system',
                      'cpu.shares', system_cpu_shares)
    cgroups.set_value('cpu', 'treadmill/core',
                      'cpu.shares', treadmill_core_cpu_shares)
    cgroups.set_value('cpu', 'treadmill/apps',
                      'cpu.shares', treadmill_apps_cpu_shares)

    cgroups.create('cpuacct', 'system')
    cgroups.create('cpuacct', 'treadmill')
    cgroups.create('cpuacct', 'treadmill/core')
    cgroups.create('cpuacct', 'treadmill/apps')

    cgroups.create('memory', 'system')
    cgroups.create('memory', 'treadmill')
    if cgroups.get_value('memory', 'treadmill',
                         'memory.use_hierarchy').strip() != '1':
        cgroups.set_value('memory', 'treadmill', 'memory.use_hierarchy', '1')
    set_memory_hardlimit('treadmill', treadmill_mem)

    oom_value = 'oom_kill_disable 0\nunder_oom 0\n'
    if cgroups.get_value('memory', 'treadmill',
                         'memory.oom_control') != oom_value:
        cgroups.set_value('memory', 'treadmill',
                          'memory.oom_control', '0')

    cgroups.create('memory', 'treadmill/core')
    cgroups.create('memory', 'treadmill/apps')

    set_memory_hardlimit('treadmill/core', treadmill_core_mem)
    cgroups.set_value('memory', 'treadmill/core',
                      'memory.soft_limit_in_bytes', treadmill_core_mem)

    # It is possible to use qualifiers in the input, for calculation of the
    # difference, get memory limits in bytes as defined in cgroup.
    total_mem_bytes = int(cgroups.get_value('memory',
                                            'treadmill',
                                            'memory.limit_in_bytes'))

    core_mem_bytes = int(cgroups.get_value('memory',
                                           'treadmill/core',
                                           'memory.limit_in_bytes'))

    apps_mem_bytes = (total_mem_bytes - core_mem_bytes)
    set_memory_hardlimit('treadmill/apps', apps_mem_bytes)


def pids_in_cgroup(subsystem, cgrp):
    """Returns the list of pids in the cgroup."""
    path = cgroups.makepath(subsystem, cgrp, 'tasks')
    with open(path) as tasks:
        return [int(line.strip()) for line in tasks.readlines() if line]


def kill_apps_in_cgroup(subsystem, cgrp, delete=False):
    """Kill all apps found in a cgroup"""
    path = cgroups.makepath(subsystem, cgrp, 'tasks')
    tasks_files = glob.glob(path)
    for tasks_file in tasks_files:
        cgrp = os.path.dirname(tasks_file)
        try:
            with open(tasks_file) as tasks:
                for pid in tasks:
                    _LOGGER.info('killing process from %r: %s',
                                 tasks_file, pid)
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except OSError as err:
                        # it is OK to fail to find the PID
                        if err.errno == errno.ESRCH:
                            continue
                        _LOGGER.exception('Unable to kill processes in %r: %s',
                                          cgrp, err)

        except IOError as err:
            # it is OK to fail if the tasks file is already gone
            if err.errno == errno.ENOENT:
                _LOGGER.debug('Skipping nonexistent cgroup %r', cgrp)
                continue
            raise

        if delete:
            for (dirname, _subdirs, _files) in os.walk(cgrp, topdown=False):
                try:
                    os.rmdir(dirname)
                except OSError as err:
                    _LOGGER.exception('Unable remove cgroup %r, %r', cgrp, err)
                    raise


def total_soft_memory_limits():
    """Add up soft memory limits."""
    total_mem = 0
    path = cgroups.makepath('memory', 'treadmill/apps/*',
                            'memory.soft_limit_in_bytes')
    mem_files = glob.glob(path)
    for mem_file in mem_files:
        try:
            with open(mem_file) as mem:
                total_mem += int(mem.read().strip())
        except IOError as err:
            # it is ok to fail if the memfile is already gone
            if err.errno == errno.ENOENT:
                continue
            _LOGGER.exception('Unable to read soft-limit %r: %s',
                              mem_file, err)
            raise

    return total_mem


def get_memory_oom_eventfd(cgrp):
    """Create, register and return a eventfd for a cgroup OOM notification.

    Args:
        cgrp ``str``: path to a cgroup root directory.

    Returns:
        ``int``: eventfd(2) filedescriptor.
    """
    # 1/ create an eventfd
    efd = eventfd.eventfd(0, eventfd.EFD_CLOEXEC)
    # 2/ open memory.oom_control
    oom_control_file = cgroups.makepath('memory', cgrp, 'memory.oom_control')
    with open(oom_control_file) as oom_control:
        # 3/ write '<eventfd_fd> <oom_control_fd> to cgroup.event_control
        cgroups.set_value(
            'memory', cgrp, 'cgroup.event_control',
            '{eventfd_fd} {oom_control_fd}'.format(
                eventfd_fd=efd,
                oom_control_fd=oom_control.fileno(),
            )
        )

    return efd


def reset_memory_limit_in_bytes():
    """Recalculate the hard memory limits.

    If any app uses more than the value we are trying to resize to, it will be
    expunged.

    :returns:
        List of unique application names to expunge from the system.
    """
    total_soft_mem = float(total_soft_memory_limits())
    total_hard_mem = int(cgroups.get_value('memory', 'treadmill/apps',
                                           'memory.limit_in_bytes'))
    basepath = cgroups.makepath('memory', 'treadmill/apps')

    _LOGGER.info('total_soft_mem: %r, total_hard_mem: %r',
                 total_soft_mem, total_hard_mem)

    expunged = []
    for f in os.listdir(basepath):
        if not os.path.isdir(os.path.join(basepath, f)):
            continue

        cgrp = os.path.join('treadmill', 'apps', f)
        soft_limit = float(cgroups.get_value('memory', cgrp,
                                             'memory.soft_limit_in_bytes'))

        percentage_of_allocated = soft_limit / total_soft_mem
        hard_limit = int(percentage_of_allocated * total_hard_mem)

        _LOGGER.info('%s: soft_limit %r, pcnt: %r, hard_limit: %r', cgrp,
                     soft_limit, percentage_of_allocated, hard_limit)

        if hard_limit < soft_limit:
            hard_limit = int(soft_limit)

        _LOGGER.debug('Setting cgroup %r hardlimit to %r', cgrp, hard_limit)
        try:
            set_memory_hardlimit(cgrp, hard_limit)

        except TreadmillCgroupError:
            # Unable to resize group, add it to the expunged groups.
            expunged.append(f)

    return expunged


def cgrp_meminfo(cgrp):
    """Grab the cgrp mem limits"""
    memusage = cgroups.get_value('memory', cgrp,
                                 'memory.usage_in_bytes')
    softmem = cgroups.get_value('memory', cgrp,
                                'memory.soft_limit_in_bytes')
    hardmem = cgroups.get_value('memory', cgrp,
                                'memory.limit_in_bytes')

    memusage = int(memusage)
    softmem = int(softmem)
    hardmem = int(hardmem)

    return (memusage, softmem, hardmem)


def cgrps_meminfo():
    """Generator to return all treadmill app memory cgrp details"""
    basepath = cgroups.makepath('memory', 'treadmill/apps')
    files = os.listdir(basepath)
    for appname in files:
        try:
            cgrp = os.path.join('treadmill/apps', appname)
            meminfo = cgrp_meminfo(cgrp)
        except IOError:
            continue

        yield (appname, meminfo)


def app_cgrp_count():
    """Get the number of apps in treadmill/apps"""
    appcount = 0
    basepath = cgroups.makepath('memory', 'treadmill/apps')
    files = os.listdir(basepath)
    for appname in files:
        fullpath = os.path.join(basepath, appname)
        if os.path.isdir(fullpath):
            appcount += 1

    return appcount


def cpu_usage(cgrp):
    """Return (in seconds) the length of time on the cpu"""
    nanosecs = cgroups.get_value('cpuacct', cgrp, 'cpuacct.usage')
    nanosecs = float(nanosecs)
    return nanosecs / NANOSECS_PER_SEC


def reset_cpu_usage(cgrp):
    """Set the cpu usage to 0"""
    with open(cgroups.makepath('cpuacct', cgrp, 'cpuacct.usage'), 'w+') as f:
        f.write('0')


def stat(subsystem, cgrp, pseudofile):
    """Calls stat the cgrp file"""
    path = cgroups.makepath(subsystem, cgrp, pseudofile)
    return os.stat(path)


def get_cpu_ratio(cgrp):
    """Get the shares cpu ratio"""
    shares = cgroups.get_cpu_shares(cgrp)
    return float(shares) / sysinfo.BMIPS_PER_CPU


def apps():
    """Returns list of apps in apps cgroup."""
    basepath = cgroups.makepath('cpu', 'treadmill/apps')
    files = os.listdir(basepath)
    return [appname for appname in files
            if os.path.isdir(os.path.join(basepath, appname))]
