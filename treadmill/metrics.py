"""Collects and reports container and host metrics."""


import os

import logging
import time

from . import cgroups
from . import cgutils
from . import psmem
from . import sysinfo


_LOGGER = logging.getLogger(__name__)

# Patterns to match Treadmill core processes, to use as filter in psmem.
#
# TODO: currently unused.
_SYSPROCS = ['s6-*', 'treadmill_disc*', 'pid1', 'app_tickets', 'app_presence',
             'app_endpoint*']

# yield metrics in chunks of 100
_METRICS_CHUNK_SIZE = 100


def read_memory_stats(cgrp):
    """Reads memory stats for the given treadmill app or system service.

    Returns tuple (usage, soft, hard)
    """
    return cgutils.cgrp_meminfo(cgrp)


def read_psmem_stats(appname, allpids):
    """Reads per-proc memory details stats."""
    cgrp = os.path.join('treadmill/apps', appname)
    group_pids = set(cgutils.pids_in_cgroup('memory', cgrp))

    # Intersection of all /proc pids (allpids) and pid in .../tasks will give
    # the set we are interested in.
    #
    # "tasks" contain thread pids that we want to filter out.
    meminfo = psmem.get_memory_usage(allpids & group_pids, use_pss=True)
    return meminfo


def read_blkio_stats(cgrp, major_minor):
    """Read bklio statistics for the given Treadmill app.
    """
    if not major_minor:
        return {
            'read_iops': 0,
            'write_iops': 0,
            'read_bps': 0,
            'write_bps': 0,
        }

    raw_blk_bps_info = cgroups.get_blkio_info(cgrp, 'bps')
    raw_blk_iops_info = cgroups.get_blkio_info(cgrp, 'iops')

    # Extract device specific information
    blk_bps_info = raw_blk_bps_info.get(major_minor,
                                        {'Read': 0, 'Write': 0})
    blk_iops_info = raw_blk_iops_info.get(major_minor,
                                          {'Read': 0, 'Write': 0})

    return {
        'read_iops': blk_iops_info['Read'],
        'write_iops': blk_iops_info['Write'],
        'read_bps': blk_bps_info['Read'],
        'write_bps': blk_bps_info['Write'],
    }


def read_load():
    """Reads server load stats."""
    with open('/proc/loadavg') as f:
        # /proc/loadavg file format:
        # 1min_avg 5min_avg 15min_avg ...
        line = f.read()
        loadavg_1min = line.split()[0]
        loadavg_5min = line.split()[1]

        return (loadavg_1min, loadavg_5min)


def read_cpu_stats(cgrp):
    """Calculate normalized CPU stats given cgroup name.

    Returns tuple of (usage, requested, usage_ratio)
    """
    cpu_usage = cgutils.cpu_usage(cgrp)
    stat = cgutils.stat('cpuacct', cgrp, 'cpuacct.usage')
    delta = time.time() - stat.st_mtime
    cgutils.reset_cpu_usage(cgrp)

    cpu_shares = cgroups.get_cpu_shares(cgrp)
    total_bogomips = sysinfo.total_bogomips()
    cpu_count = sysinfo.cpu_count()

    requested_ratio = cgutils.get_cpu_ratio(cgrp) * 100
    usage_ratio = ((cpu_usage * total_bogomips) /
                   (delta * cpu_shares) / cpu_count)
    usage = ((cpu_usage * total_bogomips) /
             (delta * sysinfo.BMIPS_PER_CPU) / cpu_count * 100)

    return (usage, requested_ratio, usage_ratio)
