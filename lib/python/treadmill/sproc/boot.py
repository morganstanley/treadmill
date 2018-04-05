"""Treadmill initialization.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
import six

from treadmill import appenv
from treadmill import cgutils
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils
from treadmill.fs import linux as fs_linux

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""
    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime',
                  envvar='TREADMILL_RUNTIME', required=True)
    @click.option('--preserve-mounts',
                  envvar='TREADMILL_HOST_MOUNTS', required=True)
    @click.option('--core-cpu-shares', default=None,
                  envvar='TREADMILL_CORE_CPU_SHARES', required=False)
    @click.option('--core-cpuset-cpus', default=None,
                  envvar='TREADMILL_CORE_CPUSET_CPUS', required=False)
    @click.option('--apps-cpuset-cpus', default=None,
                  envvar='TREADMILL_APPS_CPUSET_CPUS', required=False)
    @click.option('--core-memory-limit', default=None,
                  envvar='TREADMILL_CORE_MEMORY_LIMIT', required=False)
    def boot(approot, runtime,
             preserve_mounts,
             core_cpu_shares,
             core_cpuset_cpus, apps_cpuset_cpus,
             core_memory_limit):
        """Treadmill boot process.
        """
        _LOGGER.info('Initializing Treadmill: %s (%s)', approot, runtime)

        tm_env = appenv.AppEnvironment(approot)
        tm_env.initialize(None)

        # We preserve anything mounted on the install root (mounted by
        # plugins?) and whatever path provided on the commandline.
        fs_linux.cleanup_mounts(
            [tm_env.root + '*'] +
            preserve_mounts.split(',')
        )

        _cgroup_init(
            core_cpu_shares,
            core_cpuset_cpus, apps_cpuset_cpus,
            core_memory_limit
        )

        subproc.safe_exec(
            [
                's6_svscan',
                '-s',
                tm_env.init_dir
            ]
        )

    return boot


def _cgroup_init(treadmill_core_cpu_shares,
                 treadmill_core_cpuset_cpus,
                 treadmill_apps_cpuset_cpus,
                 treadmill_core_memory_limit):

    # TODO: Refactor this whole function:
    #       * It should be mostly folded into cgutils
    #       * There is no need to read sysinfo for CPUs, use cpuset cgroup.
    #       * There is no need to read bogomips for relative weight core/apps.
    #       * There is no need to read physical memory here, use cgroups.

    # calculate CPU shares allocation
    total_cores = sysinfo.cpu_count()
    total_cpu_shares = sysinfo.bogomips(six.moves.range(total_cores))
    if treadmill_core_cpu_shares is not None:
        core_cpu_shares = int(
            total_cpu_shares *
            utils.cpu_units(treadmill_core_cpu_shares) / 100.0
        )
        apps_cpu_shares = total_cpu_shares - core_cpu_shares
    else:
        core_cpu_shares = apps_cpu_shares = None

    _LOGGER.info(
        'Configuring CPU shares: '
        'total: %d, '
        'treadmill core: %r, '
        'treadmill apps: %r',
        total_cpu_shares,
        core_cpu_shares,
        apps_cpu_shares
    )

    # calculate memory allocation
    total_physical_mem = sysinfo.mem_info().total * 1024
    if treadmill_core_memory_limit is not None:
        core_memory = utils.size_to_bytes(treadmill_core_memory_limit)
        # XXX: tm_mem = utils.size_to_bytes(treadmill_mem)
        # XXX: if tm_mem <= 0:
        # XXX:     real_tm_mem = total_physical_mem - abs(tm_mem)
        # XXX: else:
        # XXX:     real_tm_mem = tm_mem
        treadmill_memory = total_physical_mem
        apps_memory = treadmill_memory - core_memory
    else:
        core_memory = apps_memory = None

    _LOGGER.info(
        'Configuring memory limits: '
        'total: %s, '
        'treadmill core: %r, '
        'treadmill apps: %r',
        utils.bytes_to_readable(total_physical_mem, 'B'),
        utils.bytes_to_readable(core_memory, 'B'),
        utils.bytes_to_readable(apps_memory, 'B')
    )

    # calculate cpuset cores allocation
    if treadmill_core_cpuset_cpus is not None:
        core_cpuset_cpus = _parse_cpuset_cpus(
            treadmill_core_cpuset_cpus
        )
        # TODO: Calculate from apps as treadmill - core
        apps_cpuset_cpus = _parse_cpuset_cpus(
            treadmill_apps_cpuset_cpus
        )
    else:
        core_cpuset_cpus = apps_cpuset_cpus = None

    _LOGGER.info(
        'Configuring cpuset cores: '
        'treadmill cpuset: %r, '
        'treadmill core cpuset: %r, '
        'treadmill app cpuset: %r',
        'TBD',
        core_cpuset_cpus,
        apps_cpuset_cpus
    )

    cgutils.create_treadmill_cgroups(
        core_cpu_shares,
        apps_cpu_shares,
        core_cpuset_cpus,
        apps_cpuset_cpus,
        core_memory,
        apps_memory
    )


def _parse_cpuset_cpus(cpuset_cpus):
    """Parse cpuset cores.
    """
    if not cpuset_cpus or cpuset_cpus == '-':
        return None

    cores_max = sysinfo.cpu_count() - 1
    return ','.join(
        [
            '{}{}'.format(entry, cores_max)
            if entry.endswith('-')
            else entry
            for entry in cpuset_cpus.split(',')
        ]
    )
