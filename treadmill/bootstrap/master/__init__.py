"""Treadmill master bootstrap.
"""

import pkgutil

from .. import aliases

__path__ = pkgutil.extend_path(__path__, __name__)


DEFAULTS = {
    'treadmill_host_ticket': '/treadmill/spool/krb5cc_host',
    'broken_nodes_percent': '5%',
}

ALIASES = aliases.ALIASES
