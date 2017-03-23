"""Helper module to get system related information."""

from . import exc
from . import subproc

from collections import namedtuple
import multiprocessing
import os
import socket
import time

if os.name == 'nt':
    import platform
    import psutil
    from .syscall import winapi
else:
    from . import cgroups
    from .syscall import sysinfo as syscall_sysinfo


# Equate "virtual" CPU to 5000 bogomips.
BMIPS_PER_CPU = 5000
_BYTES_IN_MB = 1024 * 1024


def _disk_usage_linux(path):
    """Return disk usage associated with path."""
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize

    return namedtuple('usage', 'total free')(total, free)


def _disk_usage_windows(path):
    """Return disk usage associated with path."""
    total, free = winapi.GetDiskFreeSpaceExW(path)

    return namedtuple('usage', 'total free')(total, free)


_MEMINFO = None


def _mem_info_linux():
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


def _mem_info_windows():
    """Return total/swap memory info"""
    global _MEMINFO  # pylint: disable=W0603
    if not _MEMINFO:
        memory = winapi.GlobalMemoryStatusEx()
        total = memory.ullTotalPhys / 1024
        swap = memory.ullTotalPageFile / 1024
        _MEMINFO = namedtuple('memory', 'total swap')(total, swap)

    return _MEMINFO


def _proc_info_linux(pid):
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


def _proc_info_windows(pid):
    """Returns process exe filename and start time."""
    try:
        process = psutil.Process(pid)
    except:
        raise exc.InvalidInputError('proc', 'pid is undefined.')

    return namedtuple('proc', 'filename ppid starttime')(process.name(),
                                                         process.ppid(),
                                                         process.create_time())


def cpu_count():
    """Return number of CPUs on the system."""
    return multiprocessing.cpu_count()


def _total_bogomips_linux():
    """Return sum of bogomips value for all CPUs."""
    total = 0
    with open('/proc/cpuinfo') as cpuinfo:
        for line in cpuinfo.read().splitlines():
            if line.startswith('bogomips'):
                total += float(line.split(':')[1])

    return int(total)


def _total_bogomips_windows():
    """Return sum of bogomips value for all CPUs."""
    # TODO(karoly) implement this
    return 5000


def hostname():
    """Hostname of the server."""
    return socket.getfqdn().lower()


def _port_range_linux():
    """Returns local port range."""
    with open('/proc/sys/net/ipv4/ip_local_port_range', 'r') as pr:
        low, high = [int(i) for i in pr.read().split()]
    return low, high


def _port_range_windows():
    """Returns local port range."""
    cmd = 'netsh.exe int ipv4 show dynamicport tcp'
    output = subproc.check_output(cmd).split('\r\n')

    low = 0
    ports = 0

    for line in output:
        if line.lower().startswith('start port'):
            low = int((line).split(':')[1])
        elif line.lower().startswith('number of ports'):
            ports = int((line).split(':')[1])

    high = ports - low + 1

    return low, high


def _kernel_ver_linux():
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


def _kernel_ver_windows():
    """Returns kernel version as major, minor, patch tuple."""
    version = platform.platform().split('-')[2]

    kver = version.split('.')

    return (int(kver[0]), int(kver[1]), int(kver[2]))


def _node_info_linux(tm_env):
    """Generate a node information report for the scheduler.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appmgr.AppEnvironment`
    """
    # Request status information from services (this may wait for the services
    # to be up).
    localdisk_status = tm_env.svc_localdisk.status(timeout=30)
    _cgroup_status = tm_env.svc_cgroup.status(timeout=30)  # noqa: F841
    _network_status = tm_env.svc_network.status(timeout=30)  # noqa: F841

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

    # Append units to all capacity info.
    info = {
        'memory': '%dM' % (memcapacity / _BYTES_IN_MB),
        'disk':  '%dM' % (localdisk_status['size'] / _BYTES_IN_MB),
        'cpu': '%d%%' % cpucapacity,
        'up_since': up_since(),
    }

    return info


def _node_info_windows(tm_env):
    """Generate a node information report for the scheduler.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appmgr.AppEnvironment`
    """
    # We normalize bogomips into logical "cores", each core == 5000 bmips.
    #
    # Each virtual "core" is then equated to 100 units.
    #
    # The formula is bmips / BMIPS_PER_CPU * 100
    cpucapacity = int(
        (total_bogomips() * 100 / BMIPS_PER_CPU)
    )
    memoryinfo = winapi.GlobalMemoryStatusEx()
    diskinfo = disk_usage(tm_env.apps_dir)

    # Append units to all capacity info.
    info = {
        'memory': '%dM' % (memoryinfo.ullAvailPhys / _BYTES_IN_MB),
        'disk':  '%dM' % (diskinfo.free / _BYTES_IN_MB),
        'cpu': '%d%%' % cpucapacity,
        'up_since': up_since(),
    }

    return info


def _uptime_linux():
    """Returns system uptime."""
    sysinfo = syscall_sysinfo.sysinfo()
    return sysinfo.uptime


def _uptime_windows():
    """Returns system uptime."""
    return winapi.GetTickCount64() / 1000


def up_since():
    """Returns time of last reboot."""
    return time.time() - uptime()


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


# pylint: disable=C0103
if os.name == 'nt':
    disk_usage = _disk_usage_windows
    mem_info = _mem_info_windows
    proc_info = _proc_info_windows
    total_bogomips = _total_bogomips_windows
    port_range = _port_range_windows
    kernel_ver = _kernel_ver_windows
    node_info = _node_info_windows
    uptime = _uptime_windows
else:
    disk_usage = _disk_usage_linux
    mem_info = _mem_info_linux
    proc_info = _proc_info_linux
    total_bogomips = _total_bogomips_linux
    port_range = _port_range_linux
    kernel_ver = _kernel_ver_linux
    node_info = _node_info_linux
    uptime = _uptime_linux
