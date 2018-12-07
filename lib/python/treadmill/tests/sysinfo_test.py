"""Unit test for sysinfo.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import os
import sys
import unittest

import mock
import six

import treadmill
import treadmill.appenv
from treadmill import sysinfo


@unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
class LinuxSysinfoTest(unittest.TestCase):
    """treadmill.sysinfo test."""

    PROC_MEMINFO = """
MemTotal:      7992596 kB
MemFree:       3572940 kB
Buffers:        202564 kB
Cached:        2371108 kB
SwapCached:          0 kB
Active:        2959388 kB
Inactive:       868476 kB
HighTotal:           0 kB
HighFree:            0 kB
LowTotal:      7992596 kB
LowFree:       3572940 kB
SwapTotal:     4064436 kB
SwapFree:      4064436 kB
Dirty:             240 kB
Writeback:           0 kB
AnonPages:     1254148 kB
Mapped:         104244 kB
Slab:           500152 kB
PageTables:      17180 kB
NFS_Unstable:        0 kB
Bounce:              0 kB
CommitLimit:  11257772 kB
Committed_AS:  2268028 kB
VmallocTotal: 34359738367 kB
VmallocUsed:    335508 kB
VmallocChunk: 34359375019 kB
HugePages_Total:     0
HugePages_Free:      0
HugePages_Rsvd:      0
Hugepagesize:     2048 kB
"""
    CPUINFO = """
processor   : 0
vendor_id   : GenuineIntel
cpu family  : 6
model       : 58
model name  :         Intel(R) Core(TM) i5-3470 CPU @ 3.20GHz
stepping    : 9
cpu MHz     : 1600.000
cache size  : 6144 KB
physical id : 0
siblings    : 4
core id     : 0
cpu cores   : 4
apicid      : 0
fpu     : yes
fpu_exception   : yes
cpuid level : 13
wp      : yes
flags       : fpu vme de pse
bogomips    : 6385.66
clflush size    : 64
cache_alignment : 64
address sizes   : 36 bits physical, 48 bits virtual
power management: [8]

processor   : 1
vendor_id   : GenuineIntel
cpu family  : 6
model       : 58
model name  :         Intel(R) Core(TM) i5-3470 CPU @ 3.20GHz
stepping    : 9
cpu MHz     : 1600.000
cache size  : 6144 KB
physical id : 0
siblings    : 4
core id     : 1
cpu cores   : 4
apicid      : 2
fpu     : yes
fpu_exception   : yes
cpuid level : 13
wp      : yes
flags       : fpu vme de pse
bogomips    : 6384.64
clflush size    : 64
cache_alignment : 64
address sizes   : 36 bits physical, 48 bits virtual
power management: [8]

processor   : 2
vendor_id   : GenuineIntel
cpu family  : 6
model       : 58
model name  :         Intel(R) Core(TM) i5-3470 CPU @ 3.20GHz
stepping    : 9
cpu MHz     : 1600.000
cache size  : 6144 KB
physical id : 0
siblings    : 4
core id     : 2
cpu cores   : 4
apicid      : 4
fpu     : yes
fpu_exception   : yes
cpuid level : 13
wp      : yes
flags       : fpu vme de pse
bogomips    : 6385.26
clflush size    : 64
cache_alignment : 64
address sizes   : 36 bits physical, 48 bits virtual
power management: [8]

processor   : 3
vendor_id   : GenuineIntel
cpu family  : 6
model       : 58
model name  :         Intel(R) Core(TM) i5-3470 CPU @ 3.20GHz
stepping    : 9
cpu MHz     : 1600.000
cache size  : 6144 KB
physical id : 0
siblings    : 4
core id     : 3
cpu cores   : 4
apicid      : 6
fpu     : yes
fpu_exception   : yes
cpuid level : 13
wp      : yes
flags       : fpu vme de pse
bogomips    : 6384.10
clflush size    : 64
cache_alignment : 64
address sizes   : 36 bits physical, 48 bits virtual
power management: [8]

"""

    def test_proc_info(self):
        """Proc info test."""
        proc_info = sysinfo.proc_info(os.getpid())
        self.assertEqual(os.getppid(), proc_info.ppid)

        # We do not check the starttime, but just verify that calling
        # proc_info twice returns same starttime, which can be used as part of
        # process signature.
        self.assertEqual(
            proc_info.starttime,
            sysinfo.proc_info(os.getpid()).starttime
        )

    @mock.patch('io.open', mock.mock_open(read_data=PROC_MEMINFO.strip()))
    def test_mem_info(self):
        """Mock test for mem info."""

        meminfo = sysinfo.mem_info()

        self.assertEqual(7992596, meminfo.total)

    @mock.patch('os.statvfs', mock.Mock())
    def test_disk_usage(self):
        """Mock test for disk usage."""
        os.statvfs.return_value = collections.namedtuple(
            'statvfs',
            'f_blocks f_bavail, f_frsize')(100, 20, 4)
        du = sysinfo.disk_usage('/var/tmp')
        os.statvfs.assert_called_with('/var/tmp')
        self.assertEqual(400, du.total)
        self.assertEqual(80, du.free)

    @mock.patch('treadmill.cgutils.get_cpuset_cores',
                mock.Mock(return_value=six.moves.range(0, 4)))
    @mock.patch('io.open', mock.mock_open(read_data=CPUINFO.strip()))
    def test_bogomips(self):
        """Mock test for mem info."""

        bogomips = sysinfo.total_bogomips()

        # bogomips  : 6385.66
        # bogomips  : 6384.64
        # bogomips  : 6385.26
        # bogomips  : 6384.10
        # -------------------
        # total     : 25539.659999999996
        self.assertEqual(25539, bogomips)

    @mock.patch('time.time', mock.Mock(return_value=50))
    @mock.patch('treadmill.cgroups.get_value',
                mock.Mock(return_value=42 * 1024**2))
    @mock.patch('treadmill.cgutils.get_cpu_shares',
                mock.Mock(return_value=2))
    @mock.patch('treadmill.sysinfo.BMIPS_PER_CPU', 1)
    @mock.patch('psutil.boot_time', mock.Mock(return_value=8))
    def test_node_info(self):
        """Test node information report generation.
        """
        # Access protected members
        # pylint: disable=W0212
        mock_tm_env = mock.Mock(
            spec_set=treadmill.appenv.AppEnvironment,
            svc_cgroup=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_localdisk=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_network=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
        )
        mock_tm_env.svc_localdisk.status.return_value = {
            'size': 100 * 1024**2,
        }

        res = sysinfo.node_info(mock_tm_env, 'linux', 'treadmill')

        mock_tm_env.svc_localdisk.status.assert_called_with(timeout=30)
        mock_tm_env.svc_cgroup.status.assert_called_with(timeout=30)
        self.assertEqual(
            res,
            {
                'cpu': '200%',    # 100% of 2 cores is available
                'memory': '42M',  # As read from cgroup
                'disk': '100M',   # As returned by localdisk service
                'up_since': 8,
                'network': mock_tm_env.svc_network.status.return_value,
                'localdisk': mock_tm_env.svc_localdisk.status.return_value,
            }
        )


if __name__ == '__main__':
    unittest.main()
