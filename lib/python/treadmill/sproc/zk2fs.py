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

    _LOGGER.info('Added instance: %s', zkpath)
    zk2fs_sync.sync_children(
        zkpath,
        need_watch_predicate=need_task_watch,
        cont_watch_predicate=cont_task_watch,
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
    @click.option('--once', help='Sync once and exit.',
                  is_flag=True, default=False)
    def zk2fs_cmd(root, endpoints, appgroups, running, scheduled, servers,
                  placement, tasks, once):
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

        zk2fs_sync.mark_ready()

        if not once:
            while True:
                time.sleep(100000)

    return zk2fs_cmd
