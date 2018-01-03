"""send collected metrics to rrd services"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill import sysinfo

_LOGGER = logging.getLogger(__name__)

# pylint: disable=C0103
last_cache = {}


def get_cpu_metrics(cpu_usage_delta, time_delta, cpu_shares):
    """calculate cpu percentage and ratio
    """
    total_bogomips = sysinfo.total_bogomips()
    cpu_count = sysinfo.available_cpu_count()

    requested_ratio = float(cpu_shares) / sysinfo.BMIPS_PER_CPU * 100
    usage_ratio = ((cpu_usage_delta * total_bogomips) /
                   (time_delta * cpu_shares) / cpu_count)
    usage = ((cpu_usage_delta * total_bogomips) /
             (time_delta * sysinfo.BMIPS_PER_CPU) / cpu_count * 100)

    return (usage, requested_ratio, usage_ratio)


def app_metrics(rrd_last, raw_metrics, sys_major_minor):
    """ get rrd readable metrics"""

    result = {
        'memusage': 0,
        'softmem': 0,
        'hardmem': 0,
        'cputotal': 0,
        'cpuusage': 0,
        'cpuusage_ratio': 0,
        'blk_read_iops': 0,
        'blk_write_iops': 0,
        'blk_read_bps': 0,
        'blk_write_bps': 0,
        'fs_used_bytes': 0,
    }

    memusage = raw_metrics['memory.usage_in_bytes']
    softmem = raw_metrics['memory.soft_limit_in_bytes']
    hardmem = raw_metrics['memory.limit_in_bytes']

    meminfo = sysinfo.mem_info()
    meminfo_total_bytes = meminfo.total * 1024

    if softmem > meminfo_total_bytes:
        softmem = meminfo_total_bytes

    if hardmem > meminfo_total_bytes:
        hardmem = meminfo_total_bytes

    result.update({
        'memusage': memusage,
        'softmem': softmem,
        'hardmem': hardmem,
    })

    cpuusage = raw_metrics['cpuacct.usage']
    timestamp = raw_metrics['timestamp']

    # cpuacct usage from cgroup is in nanosecond
    if 'cputotal' in rrd_last and rrd_last['cputotal'] != 0:
        usage_delta_in_sec = float(cpuusage - rrd_last['cputotal']) / 10e9
        time_delta = timestamp - rrd_last['timestamp']
    else:
        # just give a rough estimate in the beginning
        usage_delta_in_sec = float(cpuusage) / 10e9
        time_delta = timestamp

    cpu_share = raw_metrics['cpu.shares']
    (cpuusage_percent, _, cpuusage_ratio) = get_cpu_metrics(
        usage_delta_in_sec, time_delta, cpu_share,
    )

    result.update({
        'cputotal': cpuusage,
        'cpuusage': cpuusage_percent,
        'cpuusage_ratio': cpuusage_ratio,
    })

    # TODO: so far a container only has one blk device with major minor
    blk_iops = raw_metrics['blkio.throttle.io_serviced'].get(
        sys_major_minor, {'Read': 0, 'Write': 0}
    )
    result.update({
        'blk_read_iops': blk_iops['Read'],
        'blk_write_iops': blk_iops['Write']
    })

    blk_bps = raw_metrics['blkio.throttle.io_service_bytes'].get(
        sys_major_minor, {'Read': 0, 'Write': 0}
    )
    result.update({
        'blk_read_bps': blk_bps['Read'],
        'blk_write_bps': blk_bps['Write']
    })

    result['fs_used_bytes'] = raw_metrics.get('fs.used_bytes', 0)

    # finally append timestamp
    result['timestamp'] = raw_metrics['timestamp']

    return result


def prepare(rrdclient, rrdfile, step, interval):
    """Prepare rrdfile"""
    if not os.path.exists(rrdfile):
        rrdclient.create(rrdfile, step, interval)


def finish(rrdclient, rrdfile):
    """Finsh intersted rrdfile"""
    last_cache.pop(rrdfile, None)
    rrdclient.forget(rrdfile)
    os.unlink(rrdfile)


def update(rrdclient, rrdfile, raw_metrics, sys_maj_min):
    """Get and update metrics in rrd files"""
    updated = False
    try:
        rrd_last = last_cache.get(rrdfile, {})
        rrd_metrics = app_metrics(rrd_last, raw_metrics, sys_maj_min)
        last_cache[rrdfile] = rrd_metrics
        rrdclient.update(
            rrdfile,
            rrd_metrics,
            metrics_time=int(rrd_metrics['timestamp'])
        )
        updated = True
    except KeyError:
        _LOGGER.warning('no rrd metrics for cgroup %s', rrdfile)

    return updated
