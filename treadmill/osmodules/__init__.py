"""Treadmill platform module."""
from __future__ import absolute_import

import os
if os.name == 'nt':
    from .windows import bootstrap
    from .windows import nodeinit
else:
    from .linux import bootstrap
    from .linux import nodeinit
