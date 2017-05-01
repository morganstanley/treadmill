"""Syncronize Zookeeper with file system."""
from __future__ import absolute_import

import fnmatch
import logging
import os
import re
import shutil
import time
import zlib
import sqlite3
import tempfile

import click

from treadmill import zksync
from treadmill import fs
from treadmill import context
from treadmill import zknamespace as z
from treadmill import utils
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def _on_add_identity(zk2fs_sync, zkpath):
    """Invoked when new identity group is added."""
    _LOGGER.info('Added identity-group: %s', zkpath)
    zk2fs_sync.sync_children(zkpath, watch_data=True)


def _on_del_identity(zk2fs_sync, zkpath):
    """Invoked when identity group is removed."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed identity-group: %s', os.path.basename(fpath))
    shutil.rmtree(fpath)


def _on_add_proid(zk2fs_sync, zkpath):
    """Invoked when new proid is added to endpoints."""
    _LOGGER.info('Added proid: %s', zkpath)
    zk2fs_sync.sync_children(zkpath, watch_data=True)


def _on_del_proid(zk2fs_sync, zkpath):
    """Invoked when proid is removed from endpoints (never)."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed proid: %s', os.path.basename(fpath))
    shutil.rmtree(fpath)


def _on_add_instance(zk2fs_sync, zkpath):
    """Invoked when new instance is added to app."""

    def need_task_watch(zkpath):
        """Checks if the task is still scheduled, no need to watch if not."""
        _rest, app, instance_id = zkpath.rsplit('/', 2)
        instance = '%s#%s' % (app, instance_id)

        # If instance is in scheduled, we need the watch.
        scheduled_node = z.path.scheduled(instance)
        exists = bool(zk2fs_sync.zkclient.exists(scheduled_node))
        _LOGGER.debug('Need task watch: %s - %s', zkpath, exists)
        return exists

    def cont_task_watch(zkpath, children):
        """Do not renew watch if task is in terminal state."""
        if not children:
            return True

        last = children[-1]
        _eventtime, _appname, event, _data = last.split(',', 4)
        if event == 'deleted':
            _LOGGER.info('Terminating watch for task: %s', zkpath)
            return False

    def touch_file(zkpath):
        """Process immutable trace callback.

        Touch file and set modified time to match timestamp of the trace event.
        """
        fpath = zk2fs_sync.fpath(zkpath)
        event = os.path.basename(fpath)
        try:
            timestamp, _rest = event.split(',', 1)
            utils.touch(fpath)
            timestamp = int(float(timestamp))
            os.utime(fpath, (timestamp, timestamp))
        except ValueError:
            _LOGGER.warn('Incorrect trace format: %s', zkpath)
            zkutils.ensure_deleted(zk2fs_sync.zkclient, zkpath, recursive=True)

    _LOGGER.info('Added instance: %s', zkpath)
    zk2fs_sync.sync_children(
        zkpath,
        need_watch_predicate=need_task_watch,
        cont_watch_predicate=cont_task_watch,
        on_add=touch_file
    )


def _on_del_instance(zk2fs_sync, zkpath):
    """Invoked when instance is removed from app."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed instance: %s', os.path.basename(fpath))
    shutil.rmtree(fpath)


def _on_add_app(zk2fs_sync, zkpath, reobj):
    """Invoked when new app is added to tasks."""
    fpath = zk2fs_sync.fpath(zkpath)
    app_name = os.path.basename(fpath)
    if reobj.match(app_name):
        _LOGGER.info('Added app: %s', app_name)
        zk2fs_sync.sync_children(
            zkpath,
            on_add=lambda p: _on_add_instance(zk2fs_sync, p),
            on_del=lambda p: _on_del_instance(zk2fs_sync, p),
        )


def _on_del_app(zk2fs_sync, zkpath, reobj):
    """Invoked when app is removed from tasks."""
    fpath = zk2fs_sync.fpath(zkpath)
    app_name = os.path.basename(fpath)
    if reobj.match(app_name):
        _LOGGER.info('Removed app: %s', app_name)
        shutil.rmtree(fpath)


_CREATE_SOW_TABLE = """
create table sow (path text primary key, timestamp integer, data text, db text)
"""


_MERGE_TASKS_SCRIPT = """
attach '%s' as task_db;
BEGIN;
insert or ignore into sow
    select path, timestamp, data, '%s' from task_db.tasks;
COMMIT;
"""


def _init_sow_db(sow_db):
    """Initialize state of the world database."""
    conn = sqlite3.connect(sow_db)
    conn.execute(_CREATE_SOW_TABLE)
    conn.close()


def _copy_sow_db(sow_db):
    """Copy state of the world database to a named temporary file."""
    sow_dir = os.path.dirname(sow_db)
    with tempfile.NamedTemporaryFile(delete=False, dir=sow_dir) as f_out:
        with open(sow_db, 'rb') as f_in:
            f_out.write(f_in.read())
    return f_out.name


def _merge_sow_db(sow_db, merge_script):
    """Merge data into state of the world database using merge script."""
    sow_db_copy = _copy_sow_db(sow_db)
    with sqlite3.connect(sow_db_copy) as conn:
        conn.executescript(merge_script)
    conn.close()
    os.rename(sow_db_copy, sow_db)


def _on_add_task_db(zk2fs_sync, zkpath, sow_db):
    """Called when new task DB snapshot is added."""
    zk2fs_sync.sync_data(zkpath)
    fpath = zk2fs_sync.fpath(zkpath)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
        with open(fpath, 'rb') as f_compressed:
            f.write(zlib.decompress(f_compressed.read()))

    merge_script = _MERGE_TASKS_SCRIPT % (f.name, zkpath)
    _merge_sow_db(sow_db, merge_script)

    os.unlink(f.name)


def _on_del_task_db(zk2fs_sync, zkpath, sow_db):
    """Called when task DB snapshot is deleted."""
    fpath = zk2fs_sync.fpath(zkpath)
    fs.rm_safe(fpath)

    sow_db_copy = _copy_sow_db(sow_db)
    with sqlite3.connect(sow_db_copy) as conn:
        conn.execute("delete from sow where db = ?", (zkpath,))
    conn.close()
    os.rename(sow_db_copy, sow_db)


def init():
    """Top level command handler."""

    @click.command(name='zk2fs')
    @click.option('--root', help='Output directory.',
                  required=True)
    @click.option('--endpoints', help='Sync endpoints.',
                  is_flag=True, default=False)
    @click.option('--identity-groups', help='Sync identity-groups.',
                  is_flag=True, default=False)
    @click.option('--appgroups', help='Sync appgroups.',
                  is_flag=True, default=False)
    @click.option('--running', help='Sync running.',
                  is_flag=True, default=False)
    @click.option('--scheduled', help='Sync scheduled.',
                  is_flag=True, default=False)
    @click.option('--servers', help='Sync servers.',
                  is_flag=True, default=False)
    @click.option('--placement', help='Sync placement.',
                  is_flag=True, default=False)
    @click.option('--tasks', help='Sync trace with app pattern.')
    @click.option('--once', help='Sync once and exit.',
                  is_flag=True, default=False)
    def zk2fs_cmd(root, endpoints, identity_groups, appgroups, running,
                  scheduled, servers, placement, tasks, once):
        """Starts appcfgmgr process."""

        fs.mkdir_safe(root)
        zk2fs_sync = zksync.Zk2Fs(context.GLOBAL.zk.conn, root)

        if servers:
            zk2fs_sync.sync_children(z.path.server(), watch_data=False)

        if running:
            # Running are ephemeral, and will be added/remove automatically.
            zk2fs_sync.sync_children(z.path.running())

        if endpoints:
            zk2fs_sync.sync_children(
                z.ENDPOINTS,
                on_add=lambda p: _on_add_proid(zk2fs_sync, p),
                on_del=lambda p: _on_del_proid(zk2fs_sync, p))

        if identity_groups:
            zk2fs_sync.sync_children(
                z.IDENTITY_GROUPS,
                on_add=lambda p: _on_add_identity(zk2fs_sync, p),
                on_del=lambda p: _on_del_identity(zk2fs_sync, p))

        if scheduled:
            zk2fs_sync.sync_children(z.path.scheduled())

        if appgroups:
            zk2fs_sync.sync_children(z.path.appgroup(), watch_data=True)

        if placement:
            zk2fs_sync.sync_placement(z.path.placement(), watch_data=True)

        if tasks:
            regex = fnmatch.translate(tasks)
            _LOGGER.info('Using pattern: %s', regex)
            reobj = re.compile(regex)

            zk2fs_sync.sync_children(
                z.TASKS,
                on_add=lambda p: _on_add_app(zk2fs_sync, p, reobj),
                on_del=lambda p: _on_del_app(zk2fs_sync, p, reobj),
            )

            tasks_sow_db = os.path.join(zk2fs_sync.fsroot, '.tasks-sow.db')
            _LOGGER.info('Using tasks sow db: %s', tasks_sow_db)
            if not os.path.exists(tasks_sow_db):
                _init_sow_db(tasks_sow_db)

            zk2fs_sync.sync_children(
                z.TASKS_HISTORY,
                on_add=lambda p: _on_add_task_db(zk2fs_sync, p, tasks_sow_db),
                on_del=lambda p: _on_del_task_db(zk2fs_sync, p, tasks_sow_db),
            )

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
