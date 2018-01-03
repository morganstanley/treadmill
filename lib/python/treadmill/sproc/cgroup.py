"""Manage core level cgroups.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os

import click
import six

from treadmill import cgroups
from treadmill import cgutils
from treadmill import cli
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def _transfer_processes(subsystem, fromgroup, togroup):
    """Do the transfer of processes"""
    pids = cgroups.get_data(subsystem, fromgroup, 'tasks')
    for pid in pids.strip().split('\n'):
        try:
            cgroups.set_value(subsystem, togroup, 'tasks', pid)
        except IOError as ioe:  # pylint: disable=W0702
            if ioe.errno not in [errno.EINVAL, errno.ESRCH]:
                raise


def _unmount_cgroup(name, mounts):
    """Remove mount points of a cgroup."""
    _LOGGER.info('Unmounting cgroup %r(%r)', name, mounts)
    for mount in mounts:
        subproc.check_call(
            ['umount', '-vn', '-t', 'cgroup', mount]
        )


def _mount_cgroup(name, mount):
    """Mount a cgroup to a specified mount point."""
    _LOGGER.info('Mount cgroup %r(%r)', name, mount)
    subproc.check_call(
        ['mount', '-vn', '-t', 'cgroup', '-o', name, name, mount]
    )


def init():
    """Return top level command handler."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912

    @click.group(chain=True)
    def top():
        """Manage core cgroups."""

    @top.command(name='init')
    @click.option('--mem', callback=cli.validate_memory)
    @click.option('--mem-core', callback=cli.validate_memory)
    @click.option('--cpu', callback=cli.validate_cpu)
    @click.option('--cpu-cores', type=int)
    def cginit(mem, mem_core, cpu, cpu_cores):
        """Initialize core and system cgroups."""
        if cpu_cores > 0:
            tm_cores = six.moves.range(cpu_cores)
            tm_cpu_shares = sysinfo.bogomips(tm_cores)
            tm_core_cpu_shares = int(tm_cpu_shares * 0.01)
            tm_apps_cpu_shares = tm_cpu_shares - tm_core_cpu_shares

            total_cores = sysinfo.cpu_count()
            system_cores = six.moves.range(cpu_cores, total_cores)
            system_cpu_shares = sysinfo.bogomips(system_cores)

            _LOGGER.info('Configuring CPU limits: '
                         'treadmill cores: %d, '
                         'treadmill: %d, '
                         'treadmill core: %d, '
                         'treadmill apps: %d',
                         cpu_cores,
                         tm_cpu_shares,
                         tm_core_cpu_shares,
                         tm_apps_cpu_shares)
        else:
            total_cores = sysinfo.cpu_count()
            total_cpu_shares = sysinfo.bogomips(six.moves.range(total_cores))
            tm_cpu_shares = int(total_cpu_shares *
                                utils.cpu_units(cpu) / 100.0)
            system_cpu_shares = int(total_cpu_shares - tm_cpu_shares)
            tm_core_cpu_shares = int(tm_cpu_shares * 0.01)
            tm_apps_cpu_shares = tm_cpu_shares - tm_core_cpu_shares

            _LOGGER.info('Configuring CPU limits: '
                         'total: %d, '
                         'treadmill: %d, '
                         'system: %d, '
                         'treadmill core: %d, '
                         'treadmill apps: %d',
                         total_cpu_shares,
                         tm_cpu_shares,
                         system_cpu_shares,
                         tm_core_cpu_shares,
                         tm_apps_cpu_shares)

        tm_mem = utils.size_to_bytes(mem)
        tm_core_mem = utils.size_to_bytes(mem_core)

        total_physical_mem = sysinfo.mem_info().total * 1024

        if tm_mem <= 0:
            # For readability, instead of + tm_mem (negative).
            real_tm_mem = total_physical_mem - abs(tm_mem)
        else:
            real_tm_mem = tm_mem

        _LOGGER.info('Configuring memory limits: '
                     'total: %s, '
                     'treadmill total: %s, '
                     'treadmill core: %s',
                     utils.bytes_to_readable(total_physical_mem, 'B'),
                     utils.bytes_to_readable(real_tm_mem, 'B'),
                     utils.bytes_to_readable(tm_core_mem, 'B'))

        cgutils.create_treadmill_cgroups(system_cpu_shares,
                                         tm_cpu_shares,
                                         tm_core_cpu_shares,
                                         tm_apps_cpu_shares,
                                         cpu_cores,
                                         real_tm_mem,
                                         tm_core_mem)

    @top.command(name='exec')
    @click.option('--into', multiple=True)
    @click.argument('subcommand', nargs=-1)
    def cgexec(into, subcommand):
        """execs command into given cgroup(s)."""

        cgrps = [cgrp.split(':') for cgrp in into]
        subsystems = set([subsystem for (subsystem, path) in cgrps])
        cgroups.ensure_mounted(subsystems)

        for (subsystem, path) in cgrps:
            pathplus = path.split('=')
            if len(pathplus) == 2:
                group = os.path.dirname(pathplus[0])
                pseudofile = os.path.basename(pathplus[0])
                value = pathplus[1]
                cgroups.set_value(subsystem, group, pseudofile, value)
            else:
                cgutils.create(subsystem, path)
                cgroups.join(subsystem, path)

        if subcommand:
            execargs = list(subcommand)
            utils.sane_execvp(execargs[0], execargs)

    @top.command(name='migrate')
    @click.option('--group-from', '-f', default='')
    @click.option('--group-to', '-t', type=str)
    def cgmigrate(group_from, group_to):
        """Migrate tasks from one group to another."""
        subsystems = cgroups.available_subsystems()
        for subsystem in subsystems:
            try:
                _transfer_processes(subsystem, group_from, group_to)
            except:  # pylint: disable=W0702
                pass

    @top.command(name='cleanup')
    @click.option('-d', '--delete', is_flag=True, default=False,
                  help='Delete directories.')
    @click.option('-a', '--apps', is_flag=True, default=False,
                  help='Clean apps group.')
    @click.option('-c', '--core', is_flag=True, default=False,
                  help='Clean core group.')
    def cgcleanup(delete, apps, core):
        """Kill stale apps in cgroups."""
        subsystems = cgroups.wanted_cgroups().keys()

        cgrps = []
        if core:
            cgrps.append('treadmill/core/*')
            cgrps.append('treadmill/core')
        if apps:
            cgrps.append('treadmill/apps/*')
        if core:
            cgrps.append('treadmill/apps')
            cgrps.append('treadmill')

        _LOGGER.info('Kill stale apps in: %s:%s', subsystems, cgrps)
        for subsystem in subsystems:
            for cgrp in cgrps:
                cgutils.kill_apps_in_cgroup(subsystem, cgrp, delete)

    @top.command(name='mount')
    def cgmount():
        """Mount cgroups."""
        mounted_cgroups = cgroups.read_mounted_cgroups()
        wanted_cgroups = cgroups.wanted_cgroups()
        unwanted_cgroups = cgroups.unwanted_cgroups()

        for cgname, cgmounts in six.iteritems(mounted_cgroups):
            _LOGGER.debug('Mounted cgroup %r(%r)', cgname, cgmounts)

            if cgname in unwanted_cgroups:
                _unmount_cgroup(cgname, cgmounts)

            elif len(cgmounts) > 1:
                _LOGGER.warning('Cgroup %r has multiple mount points: %r',
                                cgname, cgmounts)

        for cgname in wanted_cgroups:
            if cgname not in mounted_cgroups:
                _mount_cgroup(cgname, wanted_cgroups[cgname])

    del cgmount
    del cgcleanup
    del cgmigrate
    del cginit
    del cgexec

    return top
