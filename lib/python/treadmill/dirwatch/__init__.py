"""Multi-platform directory watcher."""
from __future__ import absolute_import

import os

from treadmill.dirwatch.dirwatch_base import DirWatcherEvent

if os.name == 'nt':
    from treadmill.dirwatch.windows_dirwatch import \
        WindowsDirWatcher as DirWatcher
else:
    from treadmill.dirwatch.linux_dirwatch import \
        LinuxDirWatcher as DirWatcher

__all__ = ['DirWatcherEvent', 'DirWatcher']
