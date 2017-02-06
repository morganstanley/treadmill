"""
Syncronizes Zookeeper to file system.
"""


import logging
import glob
import os
import tempfile
import time

from treadmill import fs
from treadmill import exc
from treadmill import utils
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


class Zk2Fs(object):
    """Syncronize Zookeeper with file system."""

    def __init__(self, zkclient, fsroot):
        self.watches = set()
        self.processed_once = set()
        self.zkclient = zkclient
        self.fsroot = fsroot
        self.ready = False

    def mark_ready(self):
        """Mark itself as ready, typically past initial sync."""
        self.ready = True
        self._update_last()

    def _update_last(self):
        """Update .modified timestamp to indicate changes were made."""
        if self.ready:
            modified_file = os.path.join(self.fsroot, '.modified')
            utils.touch(modified_file)
            os.utime(modified_file, (time.time(), time.time()))

    def _default_on_del(self, zkpath):
        """Default callback invoked on node delete, remove file."""
        fs.rm_safe(self.fpath(zkpath))

    def _default_on_add(self, zknode):
        """Default callback invoked on node is added, default - sync data."""
        self.sync_data(zknode)

    def _write_data(self, fpath, data, stat):
        """Write Zookeeper data to filesystem.
        """
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(fpath),
                                         delete=False,
                                         prefix='.tmp',
                                         mode='w') as temp:
            temp.write(data)
            os.fchmod(temp.fileno(), 0o644)
        os.utime(temp.name, (stat.last_modified, stat.last_modified))
        os.rename(temp.name, fpath)

    def _data_watch(self, zkpath, data, stat, event):
        """Invoked when data changes."""
        fpath = self.fpath(zkpath)
        if data is None and event is None:
            _LOGGER.info('Node does not exist: %s', zkpath)
            self.watches.discard(zkpath)
            fs.rm_safe(fpath)

        elif event is not None and event.type == 'DELETED':
            _LOGGER.info('Node removed: %s', zkpath)
            self.watches.discard(zkpath)
            fs.rm_safe(fpath)
        else:
            self._write_data(fpath, data, stat)

        # Returning False will not renew the watch.
        renew = zkpath in self.watches
        _LOGGER.info('Renew watch on %s - %s', zkpath, renew)
        return renew

    def _children_watch(self, zkpath, children, watch_data,
                        on_add, on_del):
        """Callback invoked on children watch."""
        fpath = self.fpath(zkpath)
        filenames = set(map(os.path.basename,
                            glob.glob(os.path.join(fpath, '*'))))
        children = set(children)

        for extra in filenames - children:
            _LOGGER.info('Delete: %s', extra)
            self.watches.discard(z.join_zookeeper_path(zkpath, extra))
            on_del(z.join_zookeeper_path(zkpath, extra))

        if zkpath not in self.processed_once:
            self.processed_once.add(zkpath)
            for common in filenames & children:
                _LOGGER.info('Common: %s', common)

                zknode = z.join_zookeeper_path(zkpath, common)
                if watch_data:
                    self.watches.add(zknode)

                on_add(zknode)

        for missing in children - filenames:
            _LOGGER.info('Add: %s', missing)

            zknode = z.join_zookeeper_path(zkpath, missing)
            if watch_data:
                self.watches.add(zknode)

            on_add(zknode)

        return True

    def fpath(self, zkpath):
        """Returns file path to given zk node."""
        return os.path.join(self.fsroot, zkpath.lstrip('/'))

    def sync_data(self, zkpath):
        """Sync zk node data to file."""

        if zkpath in self.watches:
            @self.zkclient.DataWatch(zkpath)
            @exc.exit_on_unhandled
            def _data_watch(data, stat, event):
                """Invoked when data changes."""
                renew = self._data_watch(zkpath, data, stat, event)
                self._update_last()
                return renew

        else:
            fpath = self.fpath(zkpath)
            data, stat = self.zkclient.get(zkpath)
            self._write_data(fpath, data, stat)
            self._update_last()

    def sync_children(self, zkpath, watch_data=False,
                      on_add=None, on_del=None):
        """Sync children of zkpath to fpath."""

        _LOGGER.info('sync children: zk = %s, watch_data: %s',
                     zkpath,
                     watch_data)

        fpath = self.fpath(zkpath)
        fs.mkdir_safe(fpath)

        if not on_del:
            on_del = self._default_on_del
        if not on_add:
            on_add = self._default_on_add

        @self.zkclient.ChildrenWatch(zkpath)
        @exc.exit_on_unhandled
        def _children_watch(children):
            """Callback invoked on children watch."""
            renew = self._children_watch(
                zkpath,
                children,
                watch_data,
                on_add,
                on_del
            )

            self._update_last()
            return renew
