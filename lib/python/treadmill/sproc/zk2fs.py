"""Syncronize Zookeeper with file system."""
from __future__ import absolute_import

import logging
import os
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


def _on_add_endpoint_proid(zk2fs_sync, zkpath):
    """Invoked when new proid is added to endpoints."""
    _LOGGER.info('Added proid: %s', zkpath)
    zk2fs_sync.sync_children(zkpath, watch_data=True)


def _on_del_endpoint_proid(zk2fs_sync, zkpath):
    """Invoked when proid is removed from endpoints (never)."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed proid: %s', os.path.basename(fpath))
    shutil.rmtree(fpath)


def _on_add_trace_shard(zk2fs_sync, zkpath):
    """Invoked when new shard is added to trace."""
    _LOGGER.info('Added trace shard: %s', zkpath)
    zk2fs_sync.sync_children(
        zkpath,
        on_add=lambda p: _on_add_trace_event(zk2fs_sync, p),
        on_del=lambda p: None,
        watch_data=False
    )


def _on_del_trace_shard(zk2fs_sync, zkpath):
    """Invoked when trace shard is removed (never)."""
    del zk2fs_sync
    _LOGGER.critical('Removed trace shard: %s', zkpath)


def _on_add_trace_event(zk2fs_sync, zkpath):
    """Invoked when trace event is added."""
    fpath = zk2fs_sync.fpath(zkpath)

    # Extract timestamp.
    _name, timestamp, _rest = os.path.basename(fpath).split(',', 2)
    utime = int(float(timestamp))

    zksync.write_data(fpath, None, utime, raise_err=False)


_CREATE_SOW_TABLE = """
CREATE TABLE sow (
    path TEXT PRIMARY KEY,
    timestamp INTEGER,
    data TEXT,
    source TEXT
)
"""


_MERGE_TRACE_STMT = """
ATTACH '%s' AS temp_trace_db;
BEGIN;
INSERT OR IGNORE INTO sow
    SELECT path, timestamp, data, '%s' FROM temp_trace_db.trace;
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


def _merge_sow_db(sow_db, fname, zkpath):
    """Merge data into state of the world database using merge script."""
    merge_stmt = _MERGE_TRACE_STMT % (fname, zkpath)

    sow_db_copy = _copy_sow_db(sow_db)
    with sqlite3.connect(sow_db_copy) as conn:
        conn.executescript(merge_stmt)
    conn.close()
    os.rename(sow_db_copy, sow_db)


def _on_add_trace_db(zk2fs_sync, zkpath, sow_db):
    """Called when new trace DB snapshot is added."""
    _LOGGER.info('Added trace db snapshot: %s', zkpath)
    data, _metadata = zk2fs_sync.zkclient.get(zkpath)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
        f.write(zlib.decompress(data))

    _merge_sow_db(sow_db, f.name, zkpath)

    # Now that sow is up to date, cleanup records from file system.
    with sqlite3.connect(f.name) as conn:
        cursor = conn.cursor()
        for row in cursor.execute('SELECT path FROM trace'):
            fpath = os.path.join(zk2fs_sync.fsroot, row[0][1:])
            fs.rm_safe(fpath)

    fs.rm_safe(f.name)
    utils.touch(zk2fs_sync.fpath(zkpath))


def _on_del_trace_db(zk2fs_sync, zkpath, sow_db):
    """Called when trace DB snapshot is deleted."""
    sow_db_copy = _copy_sow_db(sow_db)
    with sqlite3.connect(sow_db_copy) as conn:
        conn.execute('DELETE FROM sow WHERE source = ?', (zkpath,))
    os.rename(sow_db_copy, sow_db)
    fs.rm_safe(zk2fs_sync.fpath(zkpath))


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
    @click.option('--trace', help='Sync trace.',
                  is_flag=True, default=False)
    @click.option('--once', help='Sync once and exit.',
                  is_flag=True, default=False)
    def zk2fs_cmd(root, endpoints, identity_groups, appgroups, running,
                  scheduled, servers, placement, trace, once):
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
                on_add=lambda p: _on_add_endpoint_proid(zk2fs_sync, p),
                on_del=lambda p: _on_del_endpoint_proid(zk2fs_sync, p))

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

        if trace:
            zk2fs_sync.sync_children(
                z.TRACE,
                on_add=lambda p: _on_add_trace_shard(zk2fs_sync, p),
                on_del=lambda p: _on_del_trace_shard(zk2fs_sync, p)
            )

            trace_sow_db = os.path.join(zk2fs_sync.fsroot, '.trace-sow.db')
            _LOGGER.info('Using trace sow db: %s', trace_sow_db)
            if not os.path.exists(trace_sow_db):
                _init_sow_db(trace_sow_db)

            zk2fs_sync.sync_children(
                z.TRACE_HISTORY,
                on_add=lambda p: _on_add_trace_db(zk2fs_sync, p, trace_sow_db),
                on_del=lambda p: _on_del_trace_db(zk2fs_sync, p, trace_sow_db),
            )

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
