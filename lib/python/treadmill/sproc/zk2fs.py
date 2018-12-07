"""Syncronize Zookeeper with file system.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import shutil
import time
import zlib
import tempfile

import click

from treadmill import fs
from treadmill import context
from treadmill import zknamespace as z
from treadmill import utils
from treadmill.trace.app import zk as app_zk
from treadmill.trace.server import zk as server_zk
from treadmill.zksync import zk2fs
from treadmill.zksync import utils as zksync_utils


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


def _on_add_placement_server(zk2fs_sync, zkpath):
    """Invoked when new server is added to placement."""
    _LOGGER.info('Added server: %s', zkpath)
    zk2fs_sync.sync_children(zkpath, watch_data=False)


def _on_del_placement_server(zk2fs_sync, zkpath):
    """Invoked when server is removed from placement."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed server: %s', os.path.basename(fpath))
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
    utime = float(timestamp)

    zksync_utils.write_data(
        fpath, None, utime, raise_err=False, tmp_dir=zk2fs_sync.tmp_dir
    )


def _on_del_trace_event(zk2fs_sync, zkpath):
    """Invoked when trace event is deleted."""
    fpath = zk2fs_sync.fpath(zkpath)
    fs.rm_safe(fpath)


def _on_add_trace_db(zk2fs_sync, zkpath, sow_dir):
    """Called when new trace DB snapshot is added."""
    _LOGGER.info('Added trace db snapshot: %s', zkpath)
    data, _metadata = zk2fs_sync.zkclient.get(zkpath)
    with tempfile.NamedTemporaryFile(delete=False,
                                     mode='wb',
                                     dir=zk2fs_sync.tmp_dir) as trace_db:
        trace_db.write(zlib.decompress(data))
    db_name = os.path.basename(zkpath)
    os.rename(trace_db.name, os.path.join(sow_dir, db_name))

    utils.touch(zk2fs_sync.fpath(zkpath))


def _on_del_trace_db(zk2fs_sync, zkpath, sow_dir):
    """Called when trace DB snapshot is deleted."""
    db_path = os.path.join(sow_dir, os.path.basename(zkpath))
    fs.rm_safe(db_path)

    fpath = zk2fs_sync.fpath(zkpath)
    fs.rm_safe(fpath)


def _sync_trace(zk2fs_sync, trace_path, trace_history_path, trace_sow_dir):
    zk2fs_sync.sync_children(
        trace_path,
        on_add=lambda p: _on_add_trace_shard(zk2fs_sync, p),
        on_del=lambda p: _on_del_trace_shard(zk2fs_sync, p)
    )

    trace_sow_dir = os.path.join(
        zk2fs_sync.fsroot, trace_sow_dir
    )
    _LOGGER.info('Using trace sow dir: %s', trace_sow_dir)
    fs.mkdir_safe(trace_sow_dir)

    zk2fs_sync.sync_children(
        trace_history_path,
        on_add=lambda p: _on_add_trace_db(
            zk2fs_sync, p, trace_sow_dir
        ),
        on_del=lambda p: _on_del_trace_db(
            zk2fs_sync, p, trace_sow_dir
        ),
    )


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
    @click.option('--servers-data', help='Sync servers and data.',
                  is_flag=True, default=False)
    @click.option('--placement', help='Sync placement.',
                  is_flag=True, default=False)
    @click.option('--trace', help='Sync trace.',
                  is_flag=True, default=False)
    @click.option('--server-trace', help='Sync server trace.',
                  is_flag=True, default=False)
    @click.option('--app-monitors', help='Sync app monitors.',
                  is_flag=True, default=False)
    @click.option('--once', help='Sync once and exit.',
                  is_flag=True, default=False)
    def zk2fs_cmd(root, endpoints, identity_groups, appgroups, running,
                  scheduled, servers, servers_data, placement, trace,
                  server_trace, app_monitors, once):
        """Starts appcfgmgr process."""

        fs.mkdir_safe(root)

        tmp_dir = os.path.join(root, '.tmp')
        fs.mkdir_safe(tmp_dir)

        zk2fs_sync = zk2fs.Zk2Fs(context.GLOBAL.zk.conn, root, tmp_dir)

        if servers or servers_data:
            zk2fs_sync.sync_children(z.path.server(), watch_data=servers_data)

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

        if app_monitors:
            zk2fs_sync.sync_children(z.path.appmonitor(), watch_data=True)

        if placement:
            zk2fs_sync.sync_children(
                z.path.placement(),
                on_add=lambda p: _on_add_placement_server(zk2fs_sync, p),
                on_del=lambda p: _on_del_placement_server(zk2fs_sync, p))

        if trace:
            _sync_trace(
                zk2fs_sync,
                z.TRACE,
                z.TRACE_HISTORY,
                app_zk.TRACE_SOW_DIR
            )

        if server_trace:
            _sync_trace(
                zk2fs_sync,
                z.SERVER_TRACE,
                z.SERVER_TRACE_HISTORY,
                server_zk.SERVER_TRACE_SOW_DIR
            )

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
