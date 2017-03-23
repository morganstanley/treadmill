"""Treadmill platform module."""


import os
if os.name == 'nt':
    from .windows import bootstrap
    from .windows import nodeinit
else:
    from .linux import bootstrap  # noqa: F401
    from .linux import nodeinit  # noqa: F401
