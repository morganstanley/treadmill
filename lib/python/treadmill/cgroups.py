"""Common cgroups management routines.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import logging
import os

import six

from . import subproc


_LOGGER = logging.getLogger(__name__)

CGROOT = '/cgroup'
PROCCGROUPS = '/proc/cgroups'
PROCMOUNTS = '/proc/mounts'

_SUBSYSTEMS2MOUNTS = None


def _mkdir_p(path):
    """proper mkdir -p implementation"""
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def create(subsystem, group):
    """mkdir cgroup"""
    fullpath = makepath(subsystem, group)
    return _mkdir_p(fullpath)


def delete(subsystem, group):
    """Delete cgroup (and all sub-cgroups)"""
    fullpath = makepath(subsystem, group)
    os.rmdir(fullpath)


def exists(subsystem, group):
    """os.path.exists the cgroup"""
    fullpath = makepath(subsystem, group)
    return os.path.exists(fullpath)


def makepath(subsystem, group, pseudofile=None):
    """Pieces together a full path of the cgroup"""
    mountpoint = get_mountpoint(subsystem)
    group = group.strip('/')
    if pseudofile:
        return os.path.join(mountpoint, group, pseudofile)
    return os.path.join(mountpoint, group)


def extractpath(path, subsystem, pseudofile=None):
    """Extract cgroup name from a cgroup path"""
    mountpoint = get_mountpoint(subsystem)

    if path.index(mountpoint) != 0:
        raise ValueError('cgroup path not started with %s', mountpoint)

    subpath = path[len(mountpoint):]

    if pseudofile is None:
        return subpath.strip('/')

    index_pseudofile = 0 - len(pseudofile)
    if subpath[index_pseudofile:] != pseudofile:
        raise ValueError('cgroup path not end with pseudofile %s', pseudofile)

    return subpath[:index_pseudofile].strip('/')


def set_value(subsystem, group, pseudofile, value):
    """Set value in cgroup pseudofile"""
    fullpath = makepath(subsystem, group, pseudofile)
    # Make sure we have utf8 strings
    if hasattr(value, 'decode'):
        value = value.decode()
    value = '{}'.format(value)
    _LOGGER.debug('setting %s => %s', fullpath, value)
    with io.open(fullpath, 'w') as f:
        f.write(value)


def get_data(subsystem, group, pseudofile):
    """Reads the data of cgroup parameter."""
    fullpath = makepath(subsystem, group, pseudofile)
    with io.open(fullpath, 'r') as f:
        return f.read().strip()


def safe_int(num_str):
    """ safely parse a value from cgroup pseudofile into an int"""
    value = int(num_str.split('\n')[0].strip(), base=10)

    # not able to have value less than 0
    if value < 0:
        value = 0

    return value


def get_value(subsystem, group, pseudofile):
    """Reads the data and convert to value of cgroup parameter.
    returns: int
    """
    data = get_data(subsystem, group, pseudofile)
    try:
        return safe_int(data)
    except ValueError:
        _LOGGER.exception('Invalid data from %s[%s]: %r',
                          subsystem, group, data)
        return 0


def get_cpu_shares(cgrp):
    """Get cpu shares"""
    return get_value('cpu', cgrp, 'cpu.shares')


def set_cpu_shares(cgrp, shares):
    """set cpu shares"""
    return set_value('cpu', cgrp, 'cpu.shares', shares)


def get_cpuset_cores(cgrp):
    """Get list of enabled cores."""
    cores = []
    cpuset = get_data('cpuset', cgrp, 'cpuset.cpus')
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


def join(subsystem, group, pid=None):
    """Move process into a specific cgroup"""
    if pid is None:
        pid = os.getpid()
    return set_value(subsystem, group, 'tasks', pid)


def mount(subsystem):
    """Mounts cgroup subsystem."""
    _LOGGER.info('Mounting cgroup: %s', subsystem)
    path = os.path.join(CGROOT, subsystem)
    if not os.path.exists(path):
        os.mkdir(path)

    subproc.check_call(['mount', '-t', 'cgroup', '-o',
                        subsystem, subsystem, path])


def ensure_mounted(subsystems):
    """Ensure that given subsystems are properly mounted."""
    mounted = mounted_subsystems()
    for subsystem in subsystems:
        if subsystem not in mounted:
            mount(subsystem)


def available_subsystems():
    """Get set of available cgroup subsystems"""
    subsystems = list()

    with io.open(PROCCGROUPS, 'r') as cgroups:
        for cgroup in cgroups:
            try:
                (subsys_name, _hierarchy,
                 _num_cgroups, enabled) = cgroup.split()
                if subsys_name[0] != '#' and enabled == '1':
                    subsystems.append(subsys_name)
            except:  # pylint: disable=W0702
                pass

    return subsystems


def mounted_subsystems():
    """Return a dict with cgroup subsystems and their mountpoints"""
    # allow global variable to cache
    global _SUBSYSTEMS2MOUNTS  # pylint: disable=W0603

    # _SUBSYSTEMS2MOUNTS is not empty
    if _SUBSYSTEMS2MOUNTS:
        return _SUBSYSTEMS2MOUNTS

    _SUBSYSTEMS2MOUNTS = {}
    with io.open(PROCMOUNTS, 'r') as mounts:
        subsystems = available_subsystems()
        for mountline in mounts:
            try:
                (_fs_spec, fs_file, fs_vfstype,
                 fs_mntops, _fs_freq, _fs_passno) = mountline.split()
                if fs_vfstype == 'cgroup':
                    for op in fs_mntops.split(','):
                        if op in subsystems:
                            _SUBSYSTEMS2MOUNTS[op] = fs_file
            except:  # pylint: disable=W0702
                pass

    return _SUBSYSTEMS2MOUNTS


def get_mountpoint(subsystem):
    """Returns mountpoint of a particular subsystem"""
    mounts = mounted_subsystems()
    return mounts[subsystem]
