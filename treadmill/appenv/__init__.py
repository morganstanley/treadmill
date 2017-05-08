"""Treadmill application environment"""

import os

if os.name == 'nt':
    from .windows_appenv import WindowsAppEnvironment as AppEnvironment
else:
    from .linux_appenv import LinuxAppEnvironment as AppEnvironment


__all__ = ['AppEnvironment']
