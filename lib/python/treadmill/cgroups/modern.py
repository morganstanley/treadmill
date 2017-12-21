"""Common cgroups management routines.
after Red Hat 7
"""

import os

import six

CGROOT = '/sys/fs/cgroup'

WANTED_GROUPS = {
    'cpu': 'cpu,cpuacct',
    'cpuacct': 'cpu,cpuacct',
    'cpuset': 'cpuset',
    'memory': 'memory',
    'blkio': 'blkio',
    'net_cls': 'net_cls,net_prio',
    'net_prio': 'net_cls,net_prio',
}

UNWANTED_GROUPS = {
    'ns',
}


def wanted_cgroups():
    """Return wanted cgroups
    """
    return {cgroup: os.path.join(CGROOT, path)
            for cgroup, path in six.iteritems(WANTED_GROUPS)}
