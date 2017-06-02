"""Treadmill spawn bootstrap.
"""

import pkgutil

from .. import aliases

__path__ = pkgutil.extend_path(__path__, __name__)


DEFAULTS = {
}

ALIASES = aliases.ALIASES
