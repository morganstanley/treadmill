"""Syncronize Zookeeper with file system."""
from __future__ import absolute_import

import fnmatch
import logging
import os
import re
import shutil
import time

import click

from .. import zksync
from .. import fs
from .. import context
from .. import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def _on_add_proid(zk2fs_sync, zkpath):
    """Invoked when new proid is added to endpoints."""
    _LOGGER.info('Added proid: %s', zkpath)
    # It is not clear if we need to watch data, as endpoints as
    # ephemeral and are added/deleted, but never modified once
    # ephemeral node is created.
    zk2fs_sync.sync_children(zkpath)


def _on_del_proid(zk2fs_sync, zkpath):
    """Invoked when proid is removed from endpoints (never)."""
    fpath = zk2fs_sync.fpath(zkpath)
    _LOGGER.info('Removed proid: %s', os.path.basename(fpath))
    shutil.rmtree(fpath)


def _on_add_instance(zk2fs_sync, zkpath):
    """Invoked when new instance is added to app."""
    _LOGGER.info('Added instance: %s', zkpath)
    zk2fs_sync.sync_children(zkpath)


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
            on_del=lambda p: _on_del_instance(zk2fs_sync, p))


def _on_del_app(zk2fs_sync, zkpath, reobj):
    """Invoked when app is removed from tasks."""
    fpath = zk2fs_sync.fpath(zkpath)
    app_name = os.path.basename(fpath)
    if reobj.match(app_name):
        _LOGGER.info('Removed app: %s', app_name)
        shutil.rmtree(fpath)


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
    @click.option('--tasks', help='Sync trace with app pattern.')
    def zk2fs_cmd(root, endpoints, appgroups, running, scheduled, servers,
                  placement, tasks):
        """Starts appcfgmgr process."""

        fs.mkdir_safe(root)
        zk2fs_sync = zksync.Zk2Fs(context.GLOBAL.zk.conn, root)

        if endpoints:
            zk2fs_sync.sync_children(
                z.ENDPOINTS,
                on_add=lambda p: _on_add_proid(zk2fs_sync, p),
                on_del=lambda p: _on_del_proid(zk2fs_sync, p))

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

        if tasks:
            regex = fnmatch.translate(tasks)
            _LOGGER.info('Using pattern: %s', regex)
            reobj = re.compile(regex)

            zk2fs_sync.sync_children(
                z.TASKS,
                on_add=lambda p: _on_add_app(zk2fs_sync, p, reobj),
                on_del=lambda p: _on_del_app(zk2fs_sync, p, reobj))

        while True:
            time.sleep(100000)

    return zk2fs_cmd
