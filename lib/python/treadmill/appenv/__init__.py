"""Treadmill application environment"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

if os.name == 'nt':
    from .windows_appenv import WindowsAppEnvironment as AppEnvironment
else:
    from .linux_appenv import LinuxAppEnvironment as AppEnvironment


__all__ = ['AppEnvironment']
