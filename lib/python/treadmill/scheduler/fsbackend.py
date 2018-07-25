"""Filesystem scheduler/master backend.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import namedtuple
import io
import logging
import os
import threading

from treadmill import dirwatch
from treadmill import fs
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill.zksync import utils as zksync_utils

from . import backend

_LOGGER = logging.getLogger(__name__)

# ZK nodes that can be ignored during snapshot
_ZK_BLACKLIST = ['//finished', '//keytabs']


def _fpath(fsroot, zkpath):
    """Returns file path to given zk node."""
    if zkpath == '/':
        return os.path.join(fsroot, '_data')

    path = zkpath.lstrip('/').split('/')
    return os.path.join(
        fsroot,
        '/'.join(['_' + d for d in path[:-1]]),
        path[-1]
    )


def _dpath(fsroot, zkpath):
    """Returns file path to given zk node."""
    if zkpath == '/':
        return fsroot

    path = zkpath.lstrip('/').split('/')
    return os.path.join(
        fsroot,
        '/'.join(['_' + d for d in path])
    )


def _write_data(fpath, data, stat):
    """Write Zookeeper data to filesystem."""
    zksync_utils.write_data(
        fpath, data, stat.last_modified
    )


def snapshot(zkclient, root, zkpath='/'):
    """Create a snapshot of ZK state to the filesystem."""
    if zkpath in _ZK_BLACKLIST:
        return

    _LOGGER.debug('snapshot %s', zkpath)

    fpath = _fpath(root, zkpath)
    fs.mkdir_safe(os.path.dirname(fpath))

    data, stat = zkclient.get(zkpath)
    _write_data(fpath, data, stat)

    children = zkclient.get_children(zkpath)
    for node in children:
        zknode = z.join_zookeeper_path(zkpath, node)
        snapshot(zkclient, root, zknode)


class FsBackend(backend.Backend):
    """Implements readonly Zookeeper based storage."""

    def __init__(self, fsroot):
        self.fsroot = fsroot
        # pylint: disable=C0103
        self.ChildrenWatch = self._childrenwatch

        self._dirwatcher = dirwatch.DirWatcher()
        self._dirwatch_dispatcher = dirwatch.DirWatcherDispatcher(
            self._dirwatcher)

        thread = threading.Thread(target=self._run_dirwatcher)
        thread.daemon = True
        thread.start()

        super(FsBackend, self).__init__()

    def _run_dirwatcher(self):
        """Dirwatcher loop."""
        while True:
            if self._dirwatcher.wait_for_events():
                self._dirwatcher.process_events()

    def _childrenwatch(self, zkpath):
        """ChildrenWatch decorator."""

        def wrap(func):
            """Decorator body."""

            def _func(_path):
                """wrapped func."""
                func(self.list(zkpath))

            dpath = _dpath(self.fsroot, zkpath)
            fs.mkdir_safe(dpath)

            self._dirwatcher.add_dir(dpath)
            self._dirwatch_dispatcher.register(dpath, {
                dirwatch.DirWatcherEvent.CREATED: _func,
                dirwatch.DirWatcherEvent.DELETED: _func,
            })

            return func

        return wrap

    def event_object(self):
        """Create new event object."""
        return threading.Event()

    def list(self, path):
        """Return path listing."""
        dpath = _dpath(self.fsroot, path)
        fs.mkdir_safe(dpath)
        try:
            children = os.listdir(dpath)
            return [e for e in children if not e.startswith('_')]
        except OSError:
            raise backend.ObjectNotFoundError()

    def get(self, path):
        """Return stored object given path.
        """
        data, _ = self.get_with_metadata(path)
        return data

    def get_with_metadata(self, path):
        """Return stored object with metadata."""
        fpath = _fpath(self.fsroot, path)
        try:
            stat = os.stat(fpath)
            meta = namedtuple('Metadata', 'ctime')(stat.st_ctime)
            with io.open(fpath) as datafile:
                return yaml.load(datafile.read()), meta
        except OSError:
            raise backend.ObjectNotFoundError()

    def exists(self, path):
        """Check if object exists."""
        fpath = _fpath(self.fsroot, path)
        return os.path.exists(fpath)

    def ensure_exists(self, path):
        """Ensure storage path exists."""
        fpath = _fpath(self.fsroot, path)
        try:
            fs.mkdir_safe(os.path.dirname(fpath))
            utils.touch(fpath)
        except OSError:
            raise backend.ObjectNotFoundError()

    def delete(self, path):
        """Delete object given the path."""
        fpath = _fpath(self.fsroot, path)
        fs.rm_safe(fpath)

    def put(self, path, value):
        """Store object at a given path."""
        fpath = _fpath(self.fsroot, path)
        try:
            fs.mkdir_safe(os.path.dirname(fpath))
            with io.open(fpath, 'w') as node:
                node.write(yaml.dump(value))
        except OSError:
            raise backend.ObjectNotFoundError()

    def update(self, path, data, check_content=True):
        """Set data into ZK node."""
        return self.put(path, data)
