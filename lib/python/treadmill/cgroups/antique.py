"""Common cgroups management routines.
before Red Hat 7
"""

import os


CGROOT = '/cgroup'
WANTED_GROUPS = [
    'cpu', 'cpuacct', 'cpuset', 'memory', 'blkio'
]
UNWANTED_GROUPS = {
    'ns',
}


def wanted_cgroups():
    """Return wanted cgroups
    """
    return {cgroup: os.path.join(CGROOT, cgroup) for cgroup in WANTED_GROUPS}
