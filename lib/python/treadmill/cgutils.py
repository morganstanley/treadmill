"""Misc cgroup utility functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import glob
import io
import logging
import os
import signal

import six

from treadmill import cgroups
from treadmill import exc
from treadmill.syscall import eventfd


_LOGGER = logging.getLogger(__name__)
NANOSECS_PER_SEC = 10**9


class TreadmillCgroupError(exc.TreadmillError):
    """Treadmill Cgroup operation error.
    """


def core_group_name(prefix):
    """Get parent group name of treadmill core service
    """
    return os.path.join(prefix, 'core')


def apps_group_name(prefix):
    """Get parent group name of treadmill apps
    """
    return os.path.join(prefix, 'apps')


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


def create_treadmill_cgroups(core_cpu_shares, apps_cpu_shares,
                             core_cpuset_cpus, apps_cpuset_cpus,
                             core_memory, apps_memory,
                             cgroup_prefix):
    """This is the core cgroup setup. Should be applied to a cleaned env.
    """
    # generate core/apps group name: treadmill, treadmill.slice etc
    core_group = core_group_name(cgroup_prefix)
    apps_group = apps_group_name(cgroup_prefix)

    # CPU and CPU Accounting (typically joined).
    create('cpu', core_group)
    create('cpu', apps_group)
    create('cpuacct', core_group)
    create('cpuacct', apps_group)

    if core_cpu_shares is not None:
        cgroups.set_value('cpu', core_group,
                          'cpu.shares', core_cpu_shares)
        cgroups.set_value('cpu', apps_group,
                          'cpu.shares', apps_cpu_shares)

    # CPU sets
    create('cpuset', core_group)
    create('cpuset', apps_group)
    cgroups.inherit_value('cpuset', core_group, 'cpuset.mems')
    cgroups.inherit_value('cpuset', apps_group, 'cpuset.mems')

    # cgroup combines duplicate cores automatically
    if core_cpuset_cpus is not None:
        cgroups.set_value('cpuset', core_group,
                          'cpuset.cpus', core_cpuset_cpus)
        cgroups.set_value('cpuset', apps_group,
                          'cpuset.cpus', apps_cpuset_cpus)
    else:
        cgroups.inherit_value('cpuset', core_group, 'cpuset.cpus')
        cgroups.inherit_value('cpuset', apps_group, 'cpuset.cpus')

    # Memory
    create('memory', core_group)
    create('memory', apps_group)

    if core_memory is not None:
        set_memory_hardlimit(core_group, core_memory)
        cgroups.set_value('memory', core_group,
                          'memory.soft_limit_in_bytes', core_memory)

        set_memory_hardlimit(apps_group, apps_memory)
        cgroups.set_value('memory', apps_group,
                          'memory.soft_limit_in_bytes', apps_memory)


def create(system, group):
    """ safely create cgroup path """
    cgroups.create(system, group)

    # if sybsystem is memory, we set move_charge_at_immigrate
    # ref: https://lwn.net/Articles/432224/
    if system == 'memory':
        memory_charge_immigrate(group)


def delete(system, group):
    """ safely delete cgroup path """
    fullpath = cgroups.makepath(system, group)

    for (dirname, _subdirs, _files) in os.walk(fullpath, topdown=False):
        cgrp = cgroups.extractpath(dirname, system)

        # free empty memory before the cgroups is destroyed
        if system == 'memory':
            memory_force_empty(cgrp)

        try:
            cgroups.delete(system, cgrp)
        except OSError as err:
            _LOGGER.exception('Unable remove cgroup %s %s, %r',
                              system, cgrp, err)
            raise err


def memory_charge_immigrate(cgrp, value=1):
    """ set memory move_charge_at_immigrate value """
    cgroups.set_value('memory', cgrp, 'memory.move_charge_at_immigrate',
                      value)


def memory_force_empty(cgrp, value=1):
    """ set memory force_empty value """
    cgroups.set_value('memory', cgrp, 'memory.force_empty',
                      value)


def pids_in_cgroup(subsystem, cgrp):
    """Returns the list of pids in the cgroup."""
    path = cgroups.makepath(subsystem, cgrp, 'tasks')
    with io.open(path) as tasks:
        return [
            int(line.strip()) for line
            in tasks.readlines() if line
        ]


def kill_apps_in_cgroup(subsystem, cgrp, delete_cgrp=False):
    """Kill all apps found in a cgroup"""
    path = cgroups.makepath(subsystem, cgrp, 'tasks')
    tasks_files = glob.glob(path)
    for tasks_file in tasks_files:
        cgrp_path = os.path.dirname(tasks_file)
        try:
            with io.open(tasks_file) as tasks:
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
                                          cgrp_path, err)

        except IOError as err:
            # it is OK to fail if the tasks file is already gone
            if err.errno == errno.ENOENT:
                _LOGGER.debug('Skipping nonexistent cgroup %r', cgrp_path)
                continue
            raise

        if delete_cgrp:
            cgrp = cgroups.extractpath(cgrp_path, subsystem)
            delete(subsystem, cgrp)


def total_soft_memory_limits(cgroup_prefix):
    """Add up soft memory limits."""
    total_mem = 0
    apps_group = apps_group_name(cgroup_prefix)
    path = cgroups.makepath('memory', '{}/*'.format(apps_group),
                            'memory.soft_limit_in_bytes')
    mem_files = glob.glob(path)
    for mem_file in mem_files:
        try:
            with io.open(mem_file) as mem:
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
    with io.open(oom_control_file) as oom_control:
        # 3/ write '<eventfd_fd> <oom_control_fd> to cgroup.event_control
        cgroups.set_value(
            'memory', cgrp, 'cgroup.event_control',
            '{eventfd_fd} {oom_control_fd}'.format(
                eventfd_fd=efd,
                oom_control_fd=oom_control.fileno(),
            )
        )

    return efd


def reset_memory_limit_in_bytes(cgroup_prefix):
    """Recalculate the hard memory limits.

    If any app uses more than the value we are trying to resize to, it will be
    expunged.

    :returns:
        List of unique application names to expunge from the system.
    """
    total_soft_mem = float(total_soft_memory_limits(cgroup_prefix))
    apps_group = apps_group_name(cgroup_prefix)
    total_hard_mem = cgroups.get_value('memory', apps_group,
                                       'memory.limit_in_bytes')
    basepath = cgroups.makepath('memory', apps_group)

    _LOGGER.info('total_soft_mem: %r, total_hard_mem: %r',
                 total_soft_mem, total_hard_mem)

    expunged = []
    for f in os.listdir(basepath):
        if not os.path.isdir(os.path.join(basepath, f)):
            continue

        cgrp = os.path.join(apps_group, f)
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


def get_stat(subsystem, cgrp):
    """ Get stat key values aooording to stat file format
    """
    pseudofile = '%s.stat' % subsystem
    stat_str = cgroups.get_data(subsystem, cgrp, pseudofile)

    stat_lines = stat_str.split('\n')
    stats = {}
    for stat_line in stat_lines:
        stat_kv = stat_line.strip().split(' ')
        stats[stat_kv[0]] = int(stat_kv[1])

    return stats


def app_cgrp_count(cgroup_prefix):
    """Get the number of apps in treadmill/apps"""
    appcount = 0
    apps_group = apps_group_name(cgroup_prefix)
    basepath = cgroups.makepath('memory', apps_group)
    files = os.listdir(basepath)
    for appname in files:
        fullpath = os.path.join(basepath, appname)
        if os.path.isdir(fullpath):
            appcount += 1

    return appcount


def per_cpu_usage(cgrp):
    """Return (in naoseconds) the length of time on each cpu"""
    usage_str = cgroups.get_data('cpuacct', cgrp, 'cpuacct.usage_percpu')
    return [int(nanosec) for nanosec in usage_str.split(' ')]


def cpu_usage(cgrp):
    """Return (in nanoseconds) the length of time on the cpu"""
    nanosecs = cgroups.get_value('cpuacct', cgrp, 'cpuacct.usage')
    return nanosecs


def reset_cpu_usage(cgrp):
    """Set the cpu usage to 0"""
    with io.open(cgroups.makepath('cpuacct', cgrp, 'cpuacct.usage'), 'w') as f:
        f.write('0')


def stat(subsystem, cgrp, pseudofile):
    """Calls stat the cgrp file"""
    path = cgroups.makepath(subsystem, cgrp, pseudofile)
    return os.stat(path)


def apps(cgroup_prefix):
    """Returns list of apps in apps cgroup."""
    apps_group = apps_group_name(cgroup_prefix)
    basepath = cgroups.makepath('cpu', apps_group)
    files = os.listdir(basepath)
    return [appname for appname in files
            if os.path.isdir(os.path.join(basepath, appname))]


def get_blkio_value(cgrp, pseudofile):
    """Get blkio basic info"""
    blkio_data = cgroups.get_data('blkio', cgrp, pseudofile)
    blkio_info = {}
    for entry in blkio_data.split('\n'):
        if not entry:
            continue

        major_minor, value = entry.split(' ')
        blkio_info[major_minor] = int(value)

    return blkio_info


def get_blkio_info(cgrp, pseudofile):
    """Get blkio throttle info."""
    blkio_data = cgroups.get_data('blkio', cgrp, pseudofile)
    blkio_info = {}
    for entry in blkio_data.split('\n'):
        if not entry or entry.startswith('Total'):
            continue

        major_minor, metric_type, value = entry.split(' ')
        blkio_info.setdefault(major_minor, {})[metric_type] = int(value)

    return blkio_info


def get_cpu_shares(cgrp):
    """Get cpu shares"""
    return cgroups.get_value('cpu', cgrp, 'cpu.shares')


def set_cpu_shares(cgrp, shares):
    """set cpu shares"""
    return cgroups.set_value('cpu', cgrp, 'cpu.shares', shares)


def get_memory_limit(cgrp):
    """Get memory size hard limit
    """
    return cgroups.get_value('memory', cgrp, 'memory.limit_in_bytes')


def get_cpuset_cores(cgrp):
    """Get list of enabled cores."""
    cores = []
    cpuset = cgroups.get_data('cpuset', cgrp, 'cpuset.cpus')
    for entry in cpuset.split(','):
        cpus = entry.split('-')
        if len(cpus) == 1:
            cores.append(int(cpus[0]))
        elif len(cpus) == 2:
            cores.extend(
                six.moves.range(
                    int(cpus[0]),
                    int(cpus[1]) + 1
                )
            )

    return cores
