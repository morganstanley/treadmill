"""Treadmill node bootstrap.
"""


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

import os
import pkgutil

from .. import aliases

__path__ = pkgutil.extend_path(__path__, __name__)

if os.name == 'nt':
    _DEFAULT_RUNTIME = 'docker'
else:
    _DEFAULT_RUNTIME = 'linux'


DEFAULTS = {
    'treadmill_runtime': _DEFAULT_RUNTIME,
    'treadmill_host_ticket': None,
    'treadmill_cpu': None,
    'treadmill_cpu_cores': None,
    'treadmill_mem': None,
    'treadmill_core_mem': None,
    'localdisk_img_location': None,
    'localdisk_img_size': None,
    'localdisk_block_dev': None,
    'block_dev_configuration': None,
    'block_dev_read_bps': None,
    'block_dev_write_bps': None,
    'block_dev_read_iops': None,
    'block_dev_write_iops': None,
    'localdisk_default_read_bps': None,
    'localdisk_default_read_iops': None,
    'localdisk_default_write_bps': None,
    'localdisk_default_write_iops': None,
}

ALIASES = aliases.ALIASES
