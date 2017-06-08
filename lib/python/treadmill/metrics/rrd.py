"""send collected metrics to rrd services"""

import logging

from treadmill import cgroups
from treadmill import cgutils
from treadmill import sysinfo

from treadmill import metrics
from treadmill import rrdutils


_LOGGER = logging.getLogger(__name__)


def get_cpu_metrics(cgrp, cpu_usage_delta, time_delta):
    """calculate cpu percentage and ratio
    """
    cpu_shares = cgroups.get_cpu_shares(cgrp)
    total_bogomips = sysinfo.total_bogomips()
    cpu_count = sysinfo.available_cpu_count()

    requested_ratio = cgutils.get_cpu_ratio(cgrp) * 100
    usage_ratio = ((cpu_usage_delta * total_bogomips) /
                   (time_delta * cpu_shares) / cpu_count)
    usage = ((cpu_usage_delta * total_bogomips) /
             (time_delta * sysinfo.BMIPS_PER_CPU) / cpu_count * 100)

    return (usage, requested_ratio, usage_ratio)


def app_metrics(cgrp, rrd_last, sys_major_minor, block_dev):
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

    _LOGGER.debug('Getting metrics from cgroup %s, sys_maj_min %s',
                  cgrp, sys_major_minor)
    raw_metrics = metrics.app_metrics(cgrp, block_dev)

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
    if 'cpu_total' in rrd_last and rrd_last['cpu_total'] != 0:
        usage_delta_in_sec = float(cpuusage - rrd_last['cpu_total']) / 10e9
        time_delta = timestamp - rrd_last['timestamp']
    else:
        # just give a rough estimate in the beginning
        usage_delta_in_sec = float(cpuusage) / 10e9
        stat = cgutils.stat('cpuacct', cgrp, 'cpuacct.usage')
        time_delta = timestamp - stat.st_mtime

    (cpuusage_percent, _, cpuusage_ratio) = get_cpu_metrics(
        cgrp, usage_delta_in_sec, time_delta
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

    result['fs_used_bytes'] = raw_metrics['fs.used_byes']

    return result


def update(rrdclient, rrdfile, cgrp, sys_maj_min, block_dev):
    """ get and update metrics in rrd files """
    rrd_last = rrdutils.lastupdate(rrdfile)
    try:
        rrd_metrics = app_metrics(cgrp, rrd_last, sys_maj_min, block_dev)
        rrdclient.update(
            rrdfile,
            rrd_metrics
        )
    except KeyError:
        _LOGGER.warn('no rrd metrics for cgroup %s', cgrp)
