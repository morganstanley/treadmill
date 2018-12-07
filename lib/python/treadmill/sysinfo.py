"""Helper module to get system related information.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import namedtuple

import io
import multiprocessing
import os
import platform
import socket

import docker
import psutil

from . import exc
from . import subproc

if os.name == 'posix':
    from . import cgroups
    from . import cgutils
else:
    # Pylint warning unable to import because it is on Windows only
    import win32api  # pylint: disable=E0401
    import win32con  # pylint: disable=E0401
    import win32security  # pylint: disable=E0401


# Equate "virtual" CPU to 5000 bogomips.
BMIPS_PER_CPU = 4000
_BYTES_IN_MB = 1024 * 1024


def _disk_usage_linux(path):
    """Return disk usage associated with path."""
    statvfs = os.statvfs(path)
    total = statvfs.f_blocks * statvfs.f_frsize
    free = statvfs.f_bavail * statvfs.f_frsize

    return namedtuple('usage', 'total free')(total, free)


def _disk_usage_windows(path):
    """Return disk usage associated with path."""
    dsk_use = psutil.disk_usage(path)

    return namedtuple('usage', 'total free')(dsk_use.total, dsk_use.free)


_MEMINFO = None


def _mem_info_linux():
    """Return total/swap memory info from /proc/meminfo."""
    global _MEMINFO  # pylint: disable=W0603
    if not _MEMINFO:
        with io.open('/proc/meminfo') as meminfo:
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
        total = psutil.virtual_memory().total // 1024
        swap = psutil.swap_memory().total // 1024
        _MEMINFO = namedtuple('memory', 'total swap')(total, swap)

    return _MEMINFO


def _proc_info_linux(pid):
    """Returns process exe filename and start time."""
    filename = None
    starttime = None
    ppid = None
    if pid is None:
        raise exc.InvalidInputError('/proc', 'pid is undefined.')

    with io.open('/proc/%s/stat' % pid, 'r') as stat:
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
    except Exception:
        raise exc.InvalidInputError('proc', 'pid is undefined.')

    return namedtuple('proc', 'filename ppid starttime')(process.name(),
                                                         process.ppid(),
                                                         process.create_time())


def cpu_count():
    """Return number of CPUs on the system."""
    return multiprocessing.cpu_count()


def _available_cpu_count_linux():
    """Return number of CPUs available for treadmill."""
    cores = cgutils.get_cpuset_cores('treadmill')
    return len(cores)


def _bogomips_linux(cores):
    """Return sum of bogomips value for cores."""
    total = 0
    with io.open('/proc/cpuinfo') as cpuinfo:
        for cpu in cpuinfo.read().split('\n\n'):
            for line in cpu.splitlines():
                if line.startswith('processor'):
                    if int(line.split(':')[1]) not in cores:
                        break
                if line.startswith('bogomips'):
                    total += float(line.split(':')[1])

    return int(total)


def _total_bogomips_linux():
    """Return sum of bogomips value for all CPUs."""
    cores = cgutils.get_cpuset_cores('treadmill')
    return _bogomips_linux(cores)


def _cpuflags_linux():
    """Return list of cpu flags."""
    with io.open('/proc/cpuinfo') as cpuinfo:
        for line in cpuinfo.read().splitlines():
            if line.startswith('flags'):
                flags = line.split(':')[1]
                return flags.split()
    return []


def _cpuflags_windows():
    """Return list of cpu flags."""
    return []


def hostname():
    """Hostname of the server."""
    host_name = socket.gethostname()
    port = 0
    family = 0
    socktype = 0
    proto = 0

    _family, _socktype, _proto, canonname, _sockaddr = socket.getaddrinfo(
        host_name,
        port,
        family,
        socktype,
        proto,
        socket.AI_CANONNAME)[0]

    return canonname.lower()


def _port_range_linux():
    """Returns local port range."""
    with io.open('/proc/sys/net/ipv4/ip_local_port_range', 'r') as f:
        low, high = [int(i) for i in f.read().split()]
    return low, high


def _port_range_windows():
    """Returns local port range."""
    cmd = 'netsh.exe int ipv4 show dynamicport tcp'
    output = subproc.check_output([cmd]).split('\r\n')

    low = 0
    ports = 0

    for line in output:
        if line.lower().startswith('start port'):
            low = int(line.split(':')[1])
        elif line.lower().startswith('number of ports'):
            ports = int(line.split(':')[1])

    high = ports - low + 1

    return low, high


def _kernel_ver_linux():
    """Returns kernel version as major, minor, patch tuple."""
    with io.open('/proc/sys/kernel/osrelease') as f:
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

        return int(kver[0]), int(kver[1]), int(kver[2])


def _kernel_ver_windows():
    """Returns kernel version as major, minor, patch tuple."""
    version = platform.platform().split('-')[2]

    kver = version.split('.')

    return int(kver[0]), int(kver[1]), int(kver[2])


def _get_docker_node_info(info):
    """Gets the node info specific to docker.
    """
    cpucapacity = int(cpu_count() * 100)
    memcapacity = (psutil.virtual_memory().total * 0.9) // _BYTES_IN_MB

    # TODO: manage disk space a little better
    client = docker.from_env()
    docker_info = client.info()
    path = docker_info['DockerRootDir']
    diskfree = disk_usage(path).free // _BYTES_IN_MB

    info.update({
        'memory': '%dM' % memcapacity,
        'disk': '%dM' % diskfree,
        'cpu': '%d%%' % cpucapacity,
    })

    return info


def _node_info_linux(tm_env, runtime, cgroup_prefix, **_kwargs):
    """Generate a node information report for the scheduler.

    :param tm_env:
        Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    :param runtime:
        Treadmill runtime in use
    :type tm_env:
        `str`
    """
    info = {
        'up_since': up_since(),
    }

    if runtime == 'linux':
        # Request status information from services (this may wait for the
        # services to be up).
        localdisk_status = tm_env.svc_localdisk.status(timeout=30)
        # FIXME: Memory and CPU available to containers should come from the
        #        cgroup service.
        _cgroup_status = tm_env.svc_cgroup.status(timeout=30)
        network_status = tm_env.svc_network.status(timeout=30)

        # We normalize bogomips into logical "cores", each core == 5000 bmips.
        # Each virtual "core" is then equated to 100 units.
        # The formula is bmips / BMIPS_PER_CPU * 100
        apps_group = cgutils.apps_group_name(cgroup_prefix)
        app_bogomips = cgutils.get_cpu_shares(apps_group)
        cpucapacity = (app_bogomips * 100) // BMIPS_PER_CPU
        memcapacity = cgroups.get_value(
            'memory',
            apps_group,
            'memory.limit_in_bytes'
        ) // _BYTES_IN_MB
        diskfree = localdisk_status['size'] // _BYTES_IN_MB

        info.update({
            'memory': '%dM' % memcapacity,
            'disk': '%dM' % diskfree,
            'cpu': '%d%%' % cpucapacity,
            'network': network_status,
            'localdisk': localdisk_status,
        })
    else:
        raise NotImplementedError(
            'Runtime {0} is not supported on Linux'.format(runtime)
        )

    return info


def _node_info_windows(_tm_env, runtime, **_kwargs):
    """Generate a node information report for the scheduler.

    :param _tm_env:
        Treadmill application environment
    :type _tm_env:
        `appenv.AppEnvironment`
    :param runtime:
        Treadmill runtime in use
    :type runtime:
        `str`
    """
    if runtime != 'docker':
        # Raising an exception will ensure windows is started with docker
        # runtime enabled
        raise NotImplementedError(
            'Runtime {0} is not supported on Windows'.format(runtime)
        )

    info = _get_docker_node_info({
        'up_since': up_since(),
    })

    dc_name = win32security.DsGetDcName()

    info.update({
        'nt.dc': dc_name['DomainControllerName'].replace('\\\\', '').lower(),
        'nt.domain': dc_name['DomainName'].lower(),
        'nt.dn': win32api.GetComputerObjectName(win32con.NameFullyQualifiedDN)
    })

    return info


def up_since():
    """Returns time of last reboot."""
    return psutil.boot_time()


# pylint: disable=C0103
if os.name == 'nt':
    disk_usage = _disk_usage_windows
    mem_info = _mem_info_windows
    proc_info = _proc_info_windows
    cpu_flags = _cpuflags_windows
    port_range = _port_range_windows
    kernel_ver = _kernel_ver_windows
    node_info = _node_info_windows
else:
    disk_usage = _disk_usage_linux
    mem_info = _mem_info_linux
    proc_info = _proc_info_linux
    cpu_flags = _cpuflags_linux
    bogomips = _bogomips_linux
    total_bogomips = _total_bogomips_linux
    port_range = _port_range_linux
    kernel_ver = _kernel_ver_linux
    node_info = _node_info_linux
    available_cpu_count = _available_cpu_count_linux
