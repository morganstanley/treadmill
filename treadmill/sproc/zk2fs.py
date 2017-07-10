"""Syncronize Zookeeper with file system."""


import logging
import os
import shutil
import time
import zlib
import sqlite3
import tempfile

import click

from treadmill import apptrace
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
        on_del=lambda p: _on_del_trace_event(zk2fs_sync, p),
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


def _on_del_trace_event(zk2fs_sync, zkpath):
    """Invoked when trace event is deleted."""
    fpath = zk2fs_sync.fpath(zkpath)
    fs.rm_safe(fpath)


def _on_add_trace_db(zk2fs_sync, zkpath, sow_dir, shard_len):
    """Called when new trace DB snapshot is added."""
    _LOGGER.info('Added trace db snapshot: %s', zkpath)
    data, _metadata = zk2fs_sync.zkclient.get(zkpath)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as trace_db:
        trace_db.write(zlib.decompress(data))

    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as sow_db:
        pass
    conn = sqlite3.connect(sow_db.name)
    conn.executescript(
        """
        ATTACH DATABASE '{trace_db}' AS trace_db;

        BEGIN TRANSACTION;
            CREATE TABLE {sow_table} (
                path text, timestamp integer, data text,
                directory text, name text
            );

            INSERT INTO {sow_table}
            SELECT path, timestamp, data,
                   SUBSTR(path, 1, {shard_len}), SUBSTR(path, {shard_len} + 2)
            FROM trace_db.trace;

            CREATE INDEX name_idx on {sow_table} (name);
            CREATE INDEX path_idx on {sow_table} (path);
        COMMIT;

        DETACH DATABASE trace_db;
        """.format(trace_db=trace_db.name,
                   sow_table=apptrace.TRACE_SOW_TABLE,
                   shard_len=shard_len)
        )
    conn.close()

    db_name = os.path.basename(zkpath)
    os.rename(sow_db.name, os.path.join(sow_dir, db_name))
    fs.rm_safe(trace_db.name)

    utils.touch(zk2fs_sync.fpath(zkpath))


def _on_del_trace_db(zk2fs_sync, zkpath, sow_dir):
    """Called when trace DB snapshot is deleted."""
    del zk2fs_sync

    db_path = os.path.join(sow_dir, os.path.basename(zkpath))
    fs.rm_safe(db_path)


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
            zk2fs_sync.sync_children(z.path.placement(), watch_data=True)

        if trace:
            zk2fs_sync.sync_children(
                z.TRACE,
                on_add=lambda p: _on_add_trace_shard(zk2fs_sync, p),
                on_del=lambda p: _on_del_trace_shard(zk2fs_sync, p)
            )

            trace_sow_dir = os.path.join(
                zk2fs_sync.fsroot, apptrace.TRACE_SOW_DIR
            )
            _LOGGER.info('Using trace sow dir: %s', trace_sow_dir)
            fs.mkdir_safe(trace_sow_dir)

            shards = z.trace_shards()
            shard_len = len(shards[0])
            assert all(len(shard) == shard_len for shard in shards), (
                'All shards should be of equal length.')

            zk2fs_sync.sync_children(
                z.TRACE_HISTORY,
                on_add=lambda p: _on_add_trace_db(
                    zk2fs_sync, p, trace_sow_dir, shard_len
                ),
                on_del=lambda p: _on_del_trace_db(
                    zk2fs_sync, p, trace_sow_dir
                ),
            )

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
