"""Treadmill node bootstrap.
"""

import pkgutil

from .. import aliases

__path__ = pkgutil.extend_path(__path__, __name__)


DEFAULTS = {
    'treadmill_host_ticket': None,
    'treadmill_cpu': None,
    'treadmill_cpu_cores': None,
    'treadmill_mem': None,
    'treadmill_core_mem': None,
    'localdisk_img_location': None,
    'localdisk_img_size': None,
    'localdisk_block_dev': None,
    'localdisk_default_read_bps': None,
    'localdisk_default_read_iops': None,
    'localdisk_default_write_bps': None,
    'localdisk_default_write_iops': None,
}

ALIASES = aliases.ALIASES
