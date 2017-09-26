"""Treadmill module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)


def __root_join(*path):
    """Joins path with location of the current file."""
    mydir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(mydir, *path))


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
