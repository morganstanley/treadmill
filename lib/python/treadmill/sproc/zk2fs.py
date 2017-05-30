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


def _on_add_trace_db(zk2fs_sync, zkpath, sow_db):
    """Called when new trace DB snapshot is added."""
    _LOGGER.info('Added trace db snapshot: %s', zkpath)
    data, _metadata = zk2fs_sync.zkclient.get(zkpath)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb', dir=sow_db) as f:
        f.write(zlib.decompress(data))

    db_path = os.path.join(sow_db, os.path.basename(zkpath))
    os.rename(f.name, db_path)

    # Now that sow is up to date, cleanup records from file system.
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for row in cursor.execute('SELECT path FROM trace'):
            fpath = os.path.join(zk2fs_sync.fsroot, row[0][1:])
            fs.rm_safe(fpath)

    fs.rm_safe(f.name)
    utils.touch(zk2fs_sync.fpath(zkpath))


def _on_del_trace_db(zk2fs_sync, zkpath, sow_db):
    """Called when trace DB snapshot is deleted."""
    del zk2fs_sync

    db_path = os.path.join(sow_db, os.path.basename(zkpath))
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
            zk2fs_sync.sync_placement(z.path.placement(), watch_data=True)

        if trace:
            zk2fs_sync.sync_children(
                z.TRACE,
                on_add=lambda p: _on_add_trace_shard(zk2fs_sync, p),
                on_del=lambda p: _on_del_trace_shard(zk2fs_sync, p)
            )

            trace_sow = os.path.join(zk2fs_sync.fsroot, '.sow', 'trace')
            _LOGGER.info('Using trace sow db: %s', trace_sow)
            fs.mkdir_safe(trace_sow)

            zk2fs_sync.sync_children(
                z.TRACE_HISTORY,
                on_add=lambda p: _on_add_trace_db(zk2fs_sync, p, trace_sow),
                on_del=lambda p: _on_del_trace_db(zk2fs_sync, p, trace_sow),
            )

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
