"""Helper module to get system related information."""
from __future__ import absolute_import

from collections import namedtuple

import multiprocessing
import os
import socket
import time

from . import cgroups
from . import exc
from . import utils
from .syscall import sysinfo as syscall_sysinfo


# Equate "virtual" CPU to 5000 bogomips.
BMIPS_PER_CPU = 5000
_BYTES_IN_MB = 1024 * 1024


def disk_usage(path):
    """Return disk usage associated with path."""
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize

    return namedtuple('usage', 'total free')(total, free)


_MEMINFO = None


def mem_info():
    """Return total/swap memory info from /proc/meminfo."""
    global _MEMINFO  # pylint: disable=W0603
    if not _MEMINFO:
        with open('/proc/meminfo') as meminfo:
            total = None
            swap = None
            for line in meminfo.read().splitlines():
                line = line[:-1]
                if line.find('MemTotal') == 0:
                    total = int(line.split()[1])
                if line.find('SwapTotal') == 0:
                    swap = int(line.split()[1])
            _MEMINFO = namedtuple('memory', 'total swap')(total, swap)

    return _MEMINFO


def proc_info(pid):
    """Returns process exe filename and start time."""
    filename = None
    starttime = None
    ppid = None
    if pid is None:
        raise exc.InvalidInputError('/proc', 'pid is undefined.')

    with open('/proc/%s/stat' % pid, 'r') as stat:
        for line in stat.read().splitlines():
            fields = line.split()
            # Filename is given in (), remove the brackets.
            filename = fields[1][1:-1]
            ppid = int(fields[3])
            starttime = int(fields[21])
    return namedtuple('proc', 'filename ppid starttime')(filename,
                                                         ppid,
                                                         starttime)


def cpu_count():
    """Return number of CPUs on the system."""
    return multiprocessing.cpu_count()


def total_bogomips():
    """Return sum of bogomips value for all CPUs."""
    total = 0
    with open('/proc/cpuinfo') as cpuinfo:
        for line in cpuinfo.read().splitlines():
            if line.startswith('bogomips'):
                total += float(line.split(':')[1])

    return int(total)


def hostname():
    """Hostname of the server."""
    return socket.getfqdn().lower()


def port_range():
    """Returns local port range."""
    with open('/proc/sys/net/ipv4/ip_local_port_range', 'r') as pr:
        low, high = [int(i) for i in pr.read().split()]
    return low, high


def kernel_ver():
    """Returns kernel version as major, minor, patch tuple."""
    with open('/proc/sys/kernel/osrelease') as f:
        kver = f.readline().split('.')[:3]
        last = len(kver)
        if last == 2:
            kver.append('0')
        last -= 1
        for char in '-_':
            kver[last] = kver[last].split(char)[0]
        try:
            int(kver[last])
        except ValueError:
            kver[last] = 0

        return (int(kver[0]), int(kver[1]), int(kver[2]))


def node_info(tm_env, max_lifetime):
    """Generate a node information report for the scheduler.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appmgr.AppEnvironment`
    :param max_lifetime:
        Maximum desired uptime of a host (by policy).
    :type max_lifetime:
        ``str``
    """
    # Request status information from services (this may wait for the services
    # to be up).
    localdisk_status = tm_env.svc_localdisk.status(timeout=30)
    _cgroup_status = tm_env.svc_cgroup.status(timeout=30)
    _network_status = tm_env.svc_network.status(timeout=30)

    # We normalize bogomips into logical "cores", each core == 5000 bmips.
    #
    # Each virtual "core" is then equated to 100 units.
    #
    # The formula is bmips / BMIPS_PER_CPU * 100
    cpucapacity = int(
        (total_bogomips() * 100 / BMIPS_PER_CPU * _app_cpu_shares_prct())
    )
    # FIXME(boysson): Memory and CPU available to containers should come from
    #                 the cgroup service.
    memcapacity = int(cgroups.get_value(
        'memory',
        'treadmill/apps',
        'memory.limit_in_bytes'
    ))

    # Calculated time when the server will expire and will be rebooted.
    sysinfo = syscall_sysinfo.sysinfo()
    max_lifetime_sec = utils.to_seconds(max_lifetime)
    valid_until = time.time() - sysinfo.uptime + max_lifetime_sec

    # Append units to all capacity info.
    info = {
        'memory': '%dM' % (memcapacity / _BYTES_IN_MB),
        'disk':  '%dM' % (localdisk_status['size'] / _BYTES_IN_MB),
        'cpu': '%d%%' % cpucapacity,
        'valid_until': valid_until,
    }

    return info


def _app_cpu_shares_prct():
    """Read cgroups to figure out the percentage of total CPU shares available
    to Treadmill applications.
    """
    # FIXME(boysson): This should probably come from the cgroup service.
    system_cpu_shares = float(
        cgroups.get_value('cpu', 'system', 'cpu.shares')
    )
    tm_cpu_shares = float(
        cgroups.get_value('cpu', 'treadmill', 'cpu.shares')
    )
    core_cpu_shares = float(
        cgroups.get_value('cpu', 'treadmill/core', 'cpu.shares')
    )
    apps_cpu_shares = float(
        cgroups.get_value('cpu', 'treadmill/apps', 'cpu.shares')
    )

    tm_percent = (tm_cpu_shares / (system_cpu_shares + tm_cpu_shares))
    apps_percent = (apps_cpu_shares / (apps_cpu_shares + core_cpu_shares))

    return apps_percent * tm_percent
