"""Common cgroups management routines.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os

from treadmill import fs
from treadmill.fs import linux as fs_linux


#: Base directory where we expect to find cgroups
CGROOT = '/sys/fs/cgroup'

#: Cgroups mount layout, modeled after after Red Hat 7.
WANTED_CGROUPS = {
    'cpu': 'cpu,cpuacct',
    'cpuacct': 'cpu,cpuacct',
    'cpuset': 'cpuset',
    'memory': 'memory',
    'blkio': 'blkio',
    'net_cls': 'net_cls,net_prio',
    'net_prio': 'net_cls,net_prio',
}

#: Where to read kernel supported cgroups
_PROC_CGROUPS = '/proc/cgroups'
_PROC_CGROUP = '/proc/{}/cgroup'

_SUBSYSTEMS2MOUNTS = None

_LOGGER = logging.getLogger(__name__)


def read_mounted_cgroups(filter_by=CGROOT):
    """Read all the currently mounted cgroups and their mount points.

    :params ``str`` filter_by:
        Filter out cgroups mounted outside of this path. Set the None/'' to
        obtain all mountpoints.
    :returns:
        ``dict`` - Map of cgroup subsystems to their mountpoints list.
    """
    availables = _available_subsystems()

    mounts = fs_linux.list_mounts()

    subsys2mnt = {}
    for mount_entry in mounts:
        if mount_entry.fs_type != 'cgroup':
            continue

        for opt in mount_entry.mnt_opts:
            if opt in availables:
                if not filter_by or mount_entry.target.startswith(filter_by):
                    subsys2mnt.setdefault(opt, []).append(mount_entry.target)

    return subsys2mnt


def mounted_subsystems():
    """Return the cached cgroup subsystems to mount dict.

    :returns:
        ``dict`` - CGroup subsystem to mountpoints list.
    """
    # allow global variable to cache
    global _SUBSYSTEMS2MOUNTS  # pylint: disable=W0603

    if _SUBSYSTEMS2MOUNTS is None:
        _SUBSYSTEMS2MOUNTS = read_mounted_cgroups(filter_by=CGROOT)

    return _SUBSYSTEMS2MOUNTS


def proc_cgroups(proc='self'):
    """Read a process' cgroups

    :returns:
        ``dict`` - Dictionary of all the process' subsystem and cgroups.
    """
    assert isinstance(proc, int) or '/' not in proc

    cgroups = {}
    with io.open(_PROC_CGROUP.format(proc), 'r') as f:
        for cgroup_line in f:
            (_id, subsys, path) = cgroup_line.strip().split(':', 2)
            cgroups[subsys] = path

    return cgroups


def makepath(subsystem, group, pseudofile=None):
    """Pieces together a full path of the cgroup.
    """
    mountpoint = _get_mountpoint(subsystem)
    group = group.strip('/')
    if pseudofile:
        return os.path.join(mountpoint, group, pseudofile)
    return os.path.join(mountpoint, group)


def extractpath(path, subsystem, pseudofile=None):
    """Extract cgroup name from a cgroup path.
    """
    mountpoint = _get_mountpoint(subsystem)

    if not path.startswith(mountpoint):
        raise ValueError('cgroup path does not start with %r' % mountpoint)

    subpath = path[len(mountpoint):]

    if pseudofile is None:
        return subpath.strip('/')
    elif not subpath.endswith(pseudofile):
        raise ValueError('cgroup path not end with pseudofile %r' % pseudofile)

    return subpath[:-len(pseudofile)].strip('/')


def create(subsystem, group):
    """Create a cgroup.
    """
    fullpath = makepath(subsystem, group)
    return fs.mkdir_safe(fullpath)


def delete(subsystem, group):
    """Delete cgroup (and all sub-cgroups).
    """
    fullpath = makepath(subsystem, group)
    os.rmdir(fullpath)


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


def get_value(subsystem, group, pseudofile):
    """Reads the data and convert to value of cgroup parameter.
    returns: int
    """
    data = get_data(subsystem, group, pseudofile)
    try:
        return _safe_int(data)
    except ValueError:
        _LOGGER.exception('Invalid data from %s:/%s[%s]: %r',
                          subsystem, group, pseudofile, data)
        return 0


def join(subsystem, group, pid=None):
    """Move process into a specific cgroup"""
    if pid is None:
        pid = os.getpid()
    return set_value(subsystem, group, 'tasks', pid)


def inherit_value(subsystem, group, pseudofile):
    """Inherit value from parent group.
    """
    parent_group = os.path.dirname(group)
    parent_value = get_data(subsystem, parent_group, pseudofile)
    set_value(subsystem, group, pseudofile, parent_value)


def _get_mountpoint(subsystem):
    """Returns mountpoint of a particular subsystem.
    """
    mounts = mounted_subsystems()
    return mounts[subsystem][0]


def _available_subsystems():
    """Get set of available cgroup subsystems.
    """
    subsystems = []

    with io.open(_PROC_CGROUPS, 'r') as cgroups:
        for cgroup in cgroups:
            (
                subsys_name,
                _hierarchy,
                _num_cgroups,
                enabled
            ) = cgroup.split()

            if subsys_name[0] != '#' and enabled == '1':
                subsystems.append(subsys_name)

    return subsystems


def _safe_int(num_str):
    """Safely parse a value from cgroup pseudofile into an int.
    """
    # Values read in cgroups could have multiple lines.
    value = int(num_str.split('\n')[0].strip(), base=10)

    # not able to have value less than 0
    if value < 0:
        value = 0

    return value
