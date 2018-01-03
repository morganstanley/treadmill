"""Treadmill distribution module.

This is helper module that interfaces with pkg_resources to resolve
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

import pkg_resources

_TREADMILL_DIST = pkg_resources.get_distribution('treadmill').location

#: Install location of this Treadmill distribution
TREADMILL = os.path.normpath(
    os.path.join(_TREADMILL_DIST, os.pardir, os.pardir)
)

if os.name == 'nt':
    _TREADMILL_SCRIPT = 'treadmill.cmd'
else:
    _TREADMILL_SCRIPT = 'treadmill'

#: Main Treadmill binary location of this Treadmill distribution
TREADMILL_BIN = os.path.join(TREADMILL, 'bin', _TREADMILL_SCRIPT)

# XXX: looks like another hack. Ideally we need to remove dependency
#      on this.
TREADMILL = os.environ.get('TREADMILL', '/opt/treadmill')
TREADMILL_BIN = os.path.join(TREADMILL, 'bin', _TREADMILL_SCRIPT)

__all__ = [
    'TREADMILL',
    'TREADMILL_BIN',
]
