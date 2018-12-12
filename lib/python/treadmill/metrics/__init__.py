"""Collects and reports container and host metrics.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import logging
import os
import time

import six

from treadmill import cgroups
from treadmill import cgutils
from treadmill import fs
from treadmill import psmem

from treadmill.fs import linux as fs_linux

NANOSECS_PER_10MILLI = 10000000

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

    Returns dict: key is pseudofile name
    """
    metric = cgrp_meminfo(cgrp)
    stats = cgutils.get_stat('memory', cgrp)
    metric['memory.stat'] = stats

    return metric


_MEMORY_TYPE = [
    'memory.failcnt',
    'memory.limit_in_bytes',
    'memory.max_usage_in_bytes',
    'memory.memsw.failcnt',
    'memory.memsw.limit_in_bytes',
    'memory.memsw.max_usage_in_bytes',
    'memory.memsw.usage_in_bytes',
    'memory.soft_limit_in_bytes',
    'memory.usage_in_bytes',
]


def cgrp_meminfo(cgrp, *pseudofiles):
    """Grab the cgrp mem limits"""

    if pseudofiles is None or not pseudofiles:
        pseudofiles = _MEMORY_TYPE

    metrics = {}
    for pseudofile in pseudofiles:
        data = cgroups.get_value('memory', cgrp, pseudofile)

        # remove memory. prefix
        metrics[pseudofile] = data

    return metrics


def read_psmem_stats(appname, allpids, cgroup_prefix):
    """Reads per-proc memory details stats."""
    apps_group = cgutils.apps_group_name(cgroup_prefix)
    cgrp = os.path.join(apps_group, appname)
    group_pids = set(cgutils.pids_in_cgroup('memory', cgrp))

    # Intersection of all /proc pids (allpids) and pid in .../tasks will give
    # the set we are interested in.
    #
    # "tasks" contain thread pids that we want to filter out.
    meminfo = psmem.get_memory_usage(allpids & group_pids, use_pss=True)
    return meminfo


_BLKIO_INFO_TYPE = [
    'blkio.throttle.io_service_bytes',
    'blkio.throttle.io_serviced',
    'blkio.io_service_bytes',
    'blkio.io_serviced',
    'blkio.io_merged',
    'blkio.io_queued',
]


def read_blkio_info_stats(cgrp, *pseudofiles):
    """Read bklio statistics for the given Treadmill app.
    """
    if pseudofiles is None or not pseudofiles:
        pseudofiles = _BLKIO_INFO_TYPE

    metrics = {}
    for pseudofile in pseudofiles:
        blkio_info = cgutils.get_blkio_info(cgrp, pseudofile)

        metrics[pseudofile] = blkio_info

    return metrics


_BLKIO_VALUE_TYPE = [
    'blkio.sectors',
    'blkio.time',
]


def read_blkio_value_stats(cgrp, *pseudofiles):
    """ read blkio value based cgroup pseudofiles
    """
    if pseudofiles is None or not pseudofiles:
        pseudofiles = _BLKIO_VALUE_TYPE

    metrics = {}
    for pseudofile in pseudofiles:
        blkio_info = cgutils.get_blkio_value(cgrp, pseudofile)

        metrics[pseudofile] = blkio_info

    return metrics


def read_load():
    """Reads server load stats."""
    with io.open('/proc/loadavg') as f:
        # /proc/loadavg file format:
        # 1min_avg 5min_avg 15min_avg ...
        line = f.read()
        loadavg_1min = line.split()[0]
        loadavg_5min = line.split()[1]

        return (loadavg_1min, loadavg_5min)


def read_cpuacct_stat(cgrp):
    """read cpuacct.stat pseudo file
    """
    divided_usage = cgutils.get_stat('cpuacct', cgrp)
    # usage in other file in nanseconds, in cpuaaac.stat is 10 miliseconds
    for name, value in six.iteritems(divided_usage):
        divided_usage[name] = value * NANOSECS_PER_10MILLI

    return divided_usage


def read_cpu_stat(cgrp):
    """read cpu.stat pseudo file
    """
    throttled_usage = cgutils.get_stat('cpu', cgrp)
    return throttled_usage


def read_cpu_system_usage():
    """ read cpu system usage.
    """
    # XXX: read /proc/stat


def read_cpu_stats(cgrp):
    """Calculate normalized CPU stats given cgroup name.

    Returns dict: key is pseudofile name
    """
    data = {}
    data['cpuacct.usage_percpu'] = cgutils.per_cpu_usage(cgrp)
    data['cpuacct.usage'] = cgutils.cpu_usage(cgrp)
    data['cpuacct.stat'] = read_cpuacct_stat(cgrp)
    data['cpu.stat'] = read_cpu_stat(cgrp)
    data['cpu.shares'] = cgutils.get_cpu_shares(cgrp)

    return data


def get_fs_usage(block_dev):
    """Get the block statistics and compute the used disk space."""
    if block_dev is None:
        return {}

    fs_info = fs_linux.blk_fs_info(block_dev)
    return {'fs.used_bytes': calc_fs_usage(fs_info)}


def calc_fs_usage(fs_info):
    """Return the used filesystem space in bytes.

    Reserved blocks are treated as used blocks because the primary goal of this
    usage metric is to indicate whether the container has to be resized.
    """
    if not fs_info:
        return 0

    blk_cnt = int(fs_info['block count'])
    free_blk_cnt = int(fs_info['free blocks'])
    blk_size = int(fs_info['block size'])

    return (blk_cnt - free_blk_cnt) * blk_size


def app_metrics(cgrp, block_dev):
    """Returns app metrics or empty dict if app not found."""
    result = {}

    try:
        result['timestamp'] = time.time()

        # merge memory stats into dict
        memory_stats = read_memory_stats(cgrp)
        result.update(memory_stats)

        # merge cpu stats into dict
        cpu_stats = read_cpu_stats(cgrp)
        result.update(cpu_stats)

        # merge blkio stats into dict
        blkio_stats = read_blkio_info_stats(cgrp)
        result.update(blkio_stats)
        blkio_stats = read_blkio_value_stats(cgrp)
        result.update(blkio_stats)

        # merge filesystem stats into dict
        fs_usage = get_fs_usage(block_dev)
        result.update(fs_usage)

    except OSError as err:
        if err.errno != errno.ENOENT:
            raise err

    except IOError as err:  # pylint: disable=duplicate-except
        if err.errno != errno.ENOENT:
            raise err

    return result
