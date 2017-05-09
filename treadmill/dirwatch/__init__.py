"""Multi-platform directory watcher."""

import os

from treadmill.dirwatch.dirwatch_base import DirWatcherEvent

if os.name == 'nt':
    from .windows_dirwatch import WindowsDirWatcher as DirWatcher
else:
    from .linux_dirwatch import LinuxDirWatcher as DirWatcher

__all__ = ['DirWatcherEvent', 'DirWatcher']
