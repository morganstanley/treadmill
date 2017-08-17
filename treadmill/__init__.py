"""Treadmill module.
"""

import os
import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)


# Global pointing to root of the source distribution.
#
# TODO: how will it work if packaged as single zip file?
if os.name == 'nt':
    _TREADMILL_SCRIPT = 'treadmill.cmd'
else:
    _TREADMILL_SCRIPT = 'treadmill'

# TODO: looks like another hack. Ideally we need to remove dependency
#       on this.
TREADMILL = os.environ.get('TREADMILL', '/opt/treadmill')
TREADMILL_BIN = os.path.join(TREADMILL, 'bin', _TREADMILL_SCRIPT)
