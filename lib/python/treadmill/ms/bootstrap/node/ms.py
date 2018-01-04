"""MS defaults."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

from .. import ms_aliases as aliases


DEFAULTS = {
    'treadmill_host_ticket': '{{ dir }}/spool/krb5cc_host',
    'treadmill_cpu': '90%',
    'treadmill_cpu_cores': 0,
    'treadmill_mem': '-2G',
    'treadmill_core_mem': '2G',
    'localdisk_img_location': '{{ dir }}',
    'localdisk_img_size': '-2G',
    'localdisk_block_dev': None,
    'block_dev_configuration':
        '/var/spool/treadmill/block_dev_configuration',
    'block_dev_read_bps': None,
    'block_dev_write_bps': None,
    'block_dev_read_iops': None,
    'block_dev_write_iops': None,
    'localdisk_default_read_bps': '20M',
    'localdisk_default_read_iops': '100',
    'localdisk_default_write_bps': '20M',
    'localdisk_default_write_iops': '100',
}

ALIASES = aliases.ALIASES


# TODO: there must be variable for that so that we do not hardcode.
def _lcl(path):
    """Return local path of the component."""
    return os.path.join('/opt/treadmill', path.strip('/'))

if os.name != 'nt':
    ALIASES.update({
        'pid1': _lcl('pid1/bin/pid1'),
        'backtick': _lcl('s6/bin/backtick'),
        'cd': _lcl('s6/bin/cd'),
        'elglob': _lcl('s6/bin/elglob'),
        'emptyenv': _lcl('s6/bin/emptyenv'),
        'execlineb': _lcl('s6/bin/execlineb'),
        'fdmove': _lcl('s6/bin/fdmove'),
        'fio': _lcl('fio/bin/fio'),
        'if': _lcl('s6/bin/if'),
        'import': _lcl('s6/bin/import'),
        'importas': _lcl('s6/bin/importas'),
        'iozone': _lcl('iozone/3.465/bin/iozone'),
        'modulecmd': _lcl('modulecmd'),
        'redirfd': _lcl('s6/bin/redirfd'),
        's6': _lcl('s6'),
        's6_envdir': _lcl('s6/bin/s6-envdir'),
        's6_envuidgid': _lcl('s6/bin/s6-envuidgid'),
        's6_log': _lcl('s6/bin/s6-log'),
        's6_setuidgid': _lcl('s6/bin/s6-setuidgid'),
        's6_svc': _lcl('s6/bin/s6-svc'),
        's6_svok': _lcl('s6/bin/s6-svok'),
        's6_svscan': _lcl('s6/bin/s6-svscan'),
        's6_svscanctl': _lcl('s6/bin/s6-svscanctl'),
        's6_svwait': _lcl('s6/bin/s6-svwait'),
        'umask': _lcl('s6/bin/umask'),
    })
