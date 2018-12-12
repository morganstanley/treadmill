"""Treadmill node bootstrap.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

from .. import aliases

if os.name == 'nt':
    _DEFAULT_RUNTIME = 'docker'
else:
    _DEFAULT_RUNTIME = 'linux'

_DEFAULT_TREADMILL_VG = 'treadmill'
_DEFAULT_HOST_TICKET = '{{ dir }}/spool/tickets/krb5cc_host'

DEFAULTS = {
    'treadmill_runtime': _DEFAULT_RUNTIME,
    'treadmill_host_ticket': _DEFAULT_HOST_TICKET,
    'treadmill_mem': None,
    'treadmill_core_mem': None,
    'treadmill_cpu_shares': None,
    'treadmill_core_cpu_shares': None,
    'system_cpuset_cores': None,
    'system_mem': None,
    'treadmill_core_cpuset_cpus': None,
    'treadmill_apps_cpuset_cpus': None,
    'treadmill_root_cgroup': 'treadmill',
    'localdisk_img_location': None,
    'localdisk_img_size': None,
    'localdisk_block_dev': None,
    'localdisk_vg_name': _DEFAULT_TREADMILL_VG,
    'block_dev_configuration': None,
    'block_dev_read_bps': None,
    'block_dev_write_bps': None,
    'block_dev_read_iops': None,
    'block_dev_write_iops': None,
    'localdisk_default_read_bps': None,
    'localdisk_default_read_iops': None,
    'localdisk_default_write_bps': None,
    'localdisk_default_write_iops': None,
    'runtime_linux_host_mounts': (
        '/,/dev*,/proc*,/sys*,/run*,/mnt*,'
    ),
    'docker_network': 'nat',
}

ALIASES = aliases.ALIASES
