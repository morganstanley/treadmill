"""Treadmill bootstrap module."""

import os

if os.name == 'nt':
    DEFAULT_INSTALL_DIR = 'c:\\'
    from .windows_bootstrap import (NodeBootstrap,
                                    MasterBootstrap,
                                    SpawnBootstrap,
                                    HAProxyBootstrap)
else:
    DEFAULT_INSTALL_DIR = '/var/tmp'
    from .linux_bootstrap import (NodeBootstrap,
                                  MasterBootstrap,
                                  SpawnBootstrap,
                                  HAProxyBootstrap)

__all__ = [
    'DEFAULT_INSTALL_DIR',
    'NodeBootstrap',
    'MasterBootstrap',
    'SpawnBootstrap',
    'HAProxyBootstrap'
]
