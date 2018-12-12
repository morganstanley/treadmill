"""Treadmill initialization.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

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
    @click.pass_context
    def boot(ctx, approot, runtime,
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
            core_memory_limit,
            ctx.obj['ROOT_CGROUP'],
        )

        subproc.safe_exec(
            [
                's6_svscan',
                '-s',
                tm_env.init_dir
            ]
        )

    return boot


def _get_cgroup_memory(treadmill_core_memory_limit, cgroup_prefix):
    """get cgroup memory parameter for treadmill core/apps group
    """
    total_physical_mem = sysinfo.mem_info().total * 1024
    total_treadmill_mem = cgutils.get_memory_limit(cgroup_prefix)

    if total_treadmill_mem > total_physical_mem:
        _LOGGER.warning(
            'memory limit for treadmill group > physical, use physical %s',
            utils.bytes_to_readable(total_treadmill_mem, 'B'),
        )
        total_treadmill_mem = total_physical_mem

    # calculate memory allocation
    if treadmill_core_memory_limit is not None:
        core_memory = utils.size_to_bytes(treadmill_core_memory_limit)
        treadmill_memory = total_treadmill_mem
        apps_memory = treadmill_memory - core_memory
    else:
        core_memory = apps_memory = None

    _LOGGER.info(
        'Configuring memory limits: '
        'phycial total: %s, '
        'treadmill total: %s, '
        'treadmill core: %s, '
        'treadmill apps: %s',
        utils.bytes_to_readable(total_physical_mem, 'B'),
        utils.bytes_to_readable(total_treadmill_mem, 'B'),
        utils.bytes_to_readable(core_memory, 'B'),
        utils.bytes_to_readable(apps_memory, 'B')
    )

    return (core_memory, apps_memory)


def _get_cgroup_cpu_shares(treadmill_core_cpu_shares,
                           treadmill_apps_cpuset_cpus):
    """get cgroup cpu shares parameter for treadmill core/apps group
    """
    # TODO: Refactor this whole function:
    #       * There is no need to read bogomips for relative weight core/apps.
    total_app_cpus = _total_cpu_cores(treadmill_apps_cpuset_cpus)
    apps_cpu_shares = sysinfo.bogomips(total_app_cpus)

    if treadmill_core_cpu_shares is not None:
        # in worst case, treadmill/core runs x% percent of treadmill/apps time
        core_cpu_shares = int(
            apps_cpu_shares *
            utils.cpu_units(treadmill_core_cpu_shares) / 100.0
        )
    else:
        core_cpu_shares = None

    _LOGGER.info(
        'Configuring CPU shares: '
        'treadmill core: %r, '
        'treadmill apps: %r',
        core_cpu_shares,
        apps_cpu_shares
    )

    return (core_cpu_shares, apps_cpu_shares)


def _get_cgroup_cpuset_cpus(treadmill_core_cpuset_cpus,
                            treadmill_apps_cpuset_cpus):
    """get cgroup cpuset cpus parameter for treadmill core/apps group
    """
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

    return (core_cpuset_cpus, apps_cpuset_cpus)


def _cgroup_init(treadmill_core_cpu_shares,
                 treadmill_core_cpuset_cpus,
                 treadmill_apps_cpuset_cpus,
                 treadmill_core_memory_limit,
                 root_cgroup):

    # calculate memory limit
    (core_memory, apps_memory) = _get_cgroup_memory(
        treadmill_core_memory_limit, root_cgroup
    )

    # calculate CPU shares allocation
    (core_cpu_shares,
     apps_cpu_shares) = _get_cgroup_cpu_shares(treadmill_core_cpu_shares,
                                               treadmill_apps_cpuset_cpus)

    # calculate cpu cores allocation
    (core_cpuset_cpus,
     apps_cpuset_cpus) = _get_cgroup_cpuset_cpus(treadmill_core_cpuset_cpus,
                                                 treadmill_apps_cpuset_cpus)

    cgutils.create_treadmill_cgroups(
        core_cpu_shares,
        apps_cpu_shares,
        core_cpuset_cpus,
        apps_cpuset_cpus,
        core_memory,
        apps_memory,
        root_cgroup,
    )


def _total_cpu_cores(cpuset_cpus):
    """Parse cpuset cores to get total core index
    """
    total_cores = sysinfo.cpu_count()
    if not cpuset_cpus or cpuset_cpus == '-':
        return set(range(total_cores))

    cores_max = sysinfo.cpu_count() - 1
    total_cores = set()
    for entry in cpuset_cpus.split(','):
        if '-' not in entry:
            total_cores.add(int(entry))
        else:
            items = entry.split('-')
            # add max value if missing
            if items[1] == '':
                items[1] = cores_max

            for i in range(int(items[0]), int(items[1]) + 1):
                total_cores.add(i)

    return total_cores


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
