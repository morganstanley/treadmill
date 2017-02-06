"""Common cgroups management routines."""


import errno
import os

import logging

from . import subproc


_LOGGER = logging.getLogger(__name__)

CGROOT = '/cgroup'
PROCCGROUPS = '/proc/cgroups'
PROCMOUNTS = '/proc/mounts'


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
    for (dirname, _subdirs, _files) in os.walk(fullpath, topdown=False):
        os.rmdir(dirname)


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


def set_value(subsystem, group, pseudofile, value):
    """Set value in cgroup pseudofile"""
    fullpath = makepath(subsystem, group, pseudofile)
    _LOGGER.debug('%s : %s', fullpath, value)
    with open(fullpath, 'w+') as f:
        f.write(str(value))


def get_value(subsystem, group, pseudofile):
    """Reads the value of cgroup parameter."""
    fullpath = makepath(subsystem, group, pseudofile)
    with open(fullpath) as f:
        return f.read().strip()


_BLKIO_THROTTLE_TYPES = {
    'bps': 'blkio.throttle.io_service_bytes',
    'iops': 'blkio.throttle.io_serviced',
}


def get_blkio_info(cgrp, kind):
    """Get blkio throttle info."""
    assert kind in _BLKIO_THROTTLE_TYPES

    blkio_data = get_value('blkio', cgrp, _BLKIO_THROTTLE_TYPES[kind])
    blkio_info = {}
    for entry in blkio_data.split('\n'):
        if not entry or entry.startswith('Total'):
            continue

        major_minor, metric_type, value = entry.split(' ')
        blkio_info.setdefault(major_minor, {})[metric_type] = int(value)

    return blkio_info


def get_cpu_shares(cgrp):
    """Get cpu shares"""
    shares = get_value('cpu', cgrp, 'cpu.shares')
    return int(shares)


def set_cpu_shares(cgrp, shares):
    """set cpu shares"""
    return set_value('cpu', cgrp, 'cpu.shares', shares)


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

    with open(PROCCGROUPS) as cgroups:
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
    subsystems2mounts = dict()

    with open(PROCMOUNTS) as mounts:
        subsystems = available_subsystems()
        for mountline in mounts:
            try:
                (_fs_spec, fs_file, fs_vfstype,
                 fs_mntops, _fs_freq, _fs_passno) = mountline.split()
                if fs_vfstype == 'cgroup':
                    for op in fs_mntops.split(','):
                        if op in subsystems:
                            subsystems2mounts[op] = fs_file
            except:  # pylint: disable=W0702
                pass

    return subsystems2mounts


def get_mountpoint(subsystem):
    """Returns mountpoint of a particular subsystem"""
    mounts = mounted_subsystems()
    return mounts[subsystem]
