"""Multi-platform directory watcher.
"""

from __future__ import absolute_import

import os

from .dirwatch_base import DirWatcherEvent

if os.name == 'nt':
    from .windows_dirwatch import WindowsDirWatcher as DirWatcher
else:
    from .linux_dirwatch import LinuxDirWatcher as DirWatcher

from .dirwatch_dispatcher import DirWatcherDispatcher

__all__ = [
    'DirWatcherEvent',
    'DirWatcher',
    'DirWatcherDispatcher'
]
