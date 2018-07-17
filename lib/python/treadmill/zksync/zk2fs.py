"""Syncronizes Zookeeper to file system.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import glob
import os
import kazoo

from treadmill import fs
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill import zkwatchers
from treadmill.zksync import utils as zksync_utils


_LOGGER = logging.getLogger(__name__)


class Zk2Fs:
    """Syncronize Zookeeper with file system."""

    def __init__(self, zkclient, fsroot, tmp_dir=None):
        self.watches = set()
        self.processed_once = set()
        self.zkclient = zkclient
        self.fsroot = fsroot
        self.tmp_dir = tmp_dir
        self.ready = False

        self.zkclient.add_listener(zkutils.exit_on_lost)

    def mark_ready(self):
        """Mark itself as ready, typically past initial sync."""
        self.ready = True
        self._update_last()

    def _update_last(self):
        """Update modify file timestamp to indicate changes were made."""
        if self.ready:
            zksync_utils.create_ready_file(self.fsroot)

    def _default_on_del(self, zkpath):
        """Default callback invoked on node delete, remove file."""
        fs.rm_safe(self.fpath(zkpath))

    def _default_on_add(self, zkpath):
        """Default callback invoked on node is added, default - sync data.

        Race condition is possible in which added node does no longer exist
        when we try to sync data.
        """
        try:
            self.sync_data(zkpath)
        except kazoo.client.NoNodeError:
            _LOGGER.warning(
                'Tried to add node that no longer exists: %s', zkpath
            )
            fpath = self.fpath(zkpath)
            fs.rm_safe(fpath)

    def _write_data(self, fpath, data, stat):
        """Write Zookeeper data to filesystem.
        """
        zksync_utils.write_data(
            fpath, data, stat.last_modified,
            raise_err=True, tmp_dir=self.tmp_dir
        )

    def _data_watch(self, zkpath, data, stat, event):
        """Invoked when data changes.
        """
        fpath = self.fpath(zkpath)
        if event is not None and event.type == 'DELETED':
            _LOGGER.info('Node deleted: %s', zkpath)
            self.watches.discard(zkpath)
            fs.rm_safe(fpath)
        elif stat is None:
            _LOGGER.info('Node does not exist: %s', zkpath)
            self.watches.discard(zkpath)
            fs.rm_safe(fpath)
        else:
            self._write_data(fpath, data, stat)

    def _filter_children_actions(self, sorted_children, sorted_filenames, add,
                                 remove, common):
        """sorts the children actions to add, remove and common."""
        num_children = len(sorted_children)
        num_filenames = len(sorted_filenames)

        child_idx = 0
        file_idx = 0

        while child_idx < num_children or file_idx < num_filenames:
            child_name = None
            if child_idx < num_children:
                child_name = sorted_children[child_idx]

            file_name = None
            if file_idx < num_filenames:
                file_name = sorted_filenames[file_idx]

            if child_name is None:
                remove.append(file_name)
                file_idx += 1

            elif file_name is None:
                add.append(child_name)
                child_idx += 1

            elif child_name == file_name:
                common.append(child_name)
                child_idx += 1
                file_idx += 1

            elif child_name < file_name:
                add.append(child_name)
                child_idx += 1

            else:
                remove.append(file_name)
                file_idx += 1

    def _children_watch(self, zkpath, children, watch_data,
                        on_add, on_del, cont_watch_predicate=None):
        """Callback invoked on children watch."""
        fpath = self.fpath(zkpath)

        sorted_children = sorted(children)
        sorted_filenames = sorted(map(os.path.basename,
                                      glob.glob(os.path.join(fpath, '*'))))

        add = []
        remove = []
        common = []

        self._filter_children_actions(sorted_children, sorted_filenames,
                                      add, remove, common)

        for node in remove:
            _LOGGER.info('Delete: %s', node)
            zknode = z.join_zookeeper_path(zkpath, node)
            self.watches.discard(zknode)
            on_del(zknode)

        if zkpath not in self.processed_once:
            self.processed_once.add(zkpath)
            for node in common:
                _LOGGER.info('Common: %s', node)

                zknode = z.join_zookeeper_path(zkpath, node)
                if watch_data:
                    self.watches.add(zknode)

                on_add(zknode)

        for node in add:
            _LOGGER.info('Add: %s', node)

            zknode = z.join_zookeeper_path(zkpath, node)
            if watch_data:
                self.watches.add(zknode)

            on_add(zknode)

        if cont_watch_predicate:
            return cont_watch_predicate(zkpath, sorted_children)

        return True

    def fpath(self, zkpath):
        """Returns file path to given zk node."""
        return os.path.join(self.fsroot, zkpath.lstrip('/'))

    def sync_data(self, zkpath):
        """Sync zk node data to file."""

        if zkpath in self.watches:
            @zkwatchers.ExistingDataWatch(self.zkclient, zkpath)
            @utils.exit_on_unhandled
            def _data_watch(data, stat, event):
                """Invoked when data changes."""
                self._data_watch(zkpath, data, stat, event)
                self._update_last()
        else:
            fpath = self.fpath(zkpath)
            data, stat = self.zkclient.get(zkpath)
            self._write_data(fpath, data, stat)
            self._update_last()

    def _make_children_watch(self, zkpath, watch_data=False,
                             on_add=None, on_del=None,
                             cont_watch_predicate=None):
        """Make children watch function."""

        _LOGGER.debug('Establish children watch on: %s', zkpath)

        @self.zkclient.ChildrenWatch(zkpath)
        @utils.exit_on_unhandled
        def _children_watch(children):
            """Callback invoked on children watch."""
            renew = self._children_watch(
                zkpath,
                children,
                watch_data,
                on_add,
                on_del,
                cont_watch_predicate=cont_watch_predicate,
            )

            self._update_last()
            return renew

    def sync_children(self, zkpath, watch_data=False,
                      on_add=None, on_del=None,
                      need_watch_predicate=None,
                      cont_watch_predicate=None):
        """Sync children of zkpath to fpath.

        need_watch_predicate decides if the watch is needed based on the
        zkpath alone.

        cont_watch_prediacate decides if the watch is needed based on content
        of zkpath children.

        To avoid race condition, both need to return False, if one of them
        returns True, watch will be set.
        """

        _LOGGER.info('sync children: zk = %s, watch_data: %s',
                     zkpath,
                     watch_data)

        fpath = self.fpath(zkpath)
        fs.mkdir_safe(fpath)

        done_file = os.path.join(fpath, '.done')
        if os.path.exists(done_file):
            _LOGGER.info('Found done file: %s, nothing to watch.', done_file)
            return

        if not on_del:
            on_del = self._default_on_del
        if not on_add:
            on_add = self._default_on_add

        need_watch = True
        if need_watch_predicate:
            need_watch = need_watch_predicate(zkpath)
            _LOGGER.info('Need watch on %s: %s', zkpath, need_watch)

        if need_watch:
            self._make_children_watch(
                zkpath, watch_data, on_add, on_del,
                cont_watch_predicate=cont_watch_predicate
            )
        else:
            try:
                children = self.zkclient.get_children(zkpath)
            except kazoo.client.NoNodeError:
                children = []

            need_watch = self._children_watch(
                zkpath,
                children,
                watch_data,
                on_add,
                on_del,
                cont_watch_predicate=cont_watch_predicate,
            )

            if need_watch:
                self._make_children_watch(
                    zkpath, watch_data, on_add, on_del,
                    cont_watch_predicate=cont_watch_predicate
                )

            self._update_last()

        if not need_watch:
            utils.touch(done_file)
