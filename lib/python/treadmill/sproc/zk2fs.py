"""Syncronize Zookeeper with file system."""
from __future__ import absolute_import

import logging
import os
import time
import shutil

import click

from .. import zksync
from .. import fs
from .. import context
from .. import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command(name='zk2fs')
    @click.option('--root', help='Output directory.',
                  required=True)
    @click.option('--endpoints', help='Sync endpoints.',
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
    def zk2fs_cmd(root, endpoints, appgroups, running, scheduled, servers,
                  placement):
        """Starts appcfgmgr process."""

        fs.mkdir_safe(root)
        zk2fs_sync = zksync.Zk2Fs(context.GLOBAL.zk.conn, root)

        if endpoints:
            def on_add(zknode):
                """Invoked when new proid is added to endpoints."""
                _LOGGER.info('Added proid: %s', zknode)
                # It is not clear if we need to watch data, as endpoints as
                # ephemeral and are added/deleted, but never modified once
                # ephemeral node is created.
                zk2fs_sync.sync_children(zknode)

            def on_del(zkpath):
                """Invoked when proid is removed from endpoints (never)."""
                fpath = zk2fs_sync._fpath(zkpath)  # pylint: disable=W0212
                _LOGGER.info('Removed proid: %s', os.path.basename(fpath))
                shutil.rmtree(fpath)

            zk2fs_sync.sync_children(z.ENDPOINTS,
                                     on_add=on_add, on_del=on_del)

        if running:
            # Running are ephemeral, and will be added/remove automatically.
            zk2fs_sync.sync_children(z.path.running())

        if scheduled:
            zk2fs_sync.sync_children(z.path.scheduled())

        if appgroups:
            zk2fs_sync.sync_children(z.path.appgroup(), watch_data=True)

        if servers:
            zk2fs_sync.sync_children(z.path.server(), watch_data=False)

        if placement:
            zk2fs_sync.sync_placement(z.path.placement(), watch_data=True)

        while True:
            time.sleep(100000)

    return zk2fs_cmd
