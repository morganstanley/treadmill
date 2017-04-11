"""Treadmill bootstrap module."""
from __future__ import absolute_import

import os

if os.name == 'nt':
    DEFAULT_INSTALL_DIR = 'c:\\'
    from treadmill.bootstrap.windows_bootstrap import NodeBootstrap, \
        MasterBootstrap, SpawnBootstrap, HAProxyBootstrap
else:
    DEFAULT_INSTALL_DIR = '/var/tmp'
    from treadmill.bootstrap.linux_bootstrap import NodeBootstrap, \
        MasterBootstrap, SpawnBootstrap, HAProxyBootstrap

__all__ = [
    'DEFAULT_INSTALL_DIR',
    'NodeBootstrap',
    'MasterBootstrap',
    'SpawnBootstrap',
    'HAProxyBootstrap'
]
