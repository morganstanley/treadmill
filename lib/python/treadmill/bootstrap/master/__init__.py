"""Treadmill master bootstrap.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .. import aliases


DEFAULTS = {
    'treadmill_host_ticket': '/treadmill/spool/krb5cc_host',
    'broken_nodes_percent': '5%',
    'restart_interval': 300,
    'restart_limit': 5,
}

ALIASES = aliases.ALIASES
