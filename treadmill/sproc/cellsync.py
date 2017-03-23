"""Syncronizes cell Zookeeper with LDAP data."""


import importlib
import logging
import os
import time

import click

from treadmill import context
from treadmill import admin
from treadmill import zkutils
from treadmill import sysinfo
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def _remove_id(entity):
    """Remove _id from the payload."""
    del entity['_id']


def _sync_collection(zkclient, entities, zkpath, match=None):
    """Syncs ldap collection to Zookeeper."""
    _LOGGER.info('Sync: %s', zkpath)

    zkclient.ensure_path(zkpath)

    in_zk = zkclient.get_children(zkpath)
    names = [entity['_id'] for entity in entities]

    for entity in entities:
        _remove_id(entity)

    for extra in set(in_zk) - set(names):
        _LOGGER.debug('Delete: %s', extra)
        zkutils.ensure_deleted(zkclient, z.join_zookeeper_path(zkpath, extra))

    # Add or update current app-groups
    for name, entity in zip(names, entities):
        zkname = name
        if match:
            zkname = match(name, entity)
            if not zkname:
                _LOGGER.debug('Skip: %s', name)
                continue

        if zkutils.put(zkclient, z.join_zookeeper_path(zkpath, zkname),
                       entity, check_content=True):
            _LOGGER.info('Update: %s', zkname)
        else:
            _LOGGER.info('Up to date: %s', zkname)


def _sync_allocations(zkclient, allocations):
    """Syncronize allocations."""
    filtered = []
    for alloc in allocations:
        _LOGGER.info('Sync allocation: %s', alloc)
        name, _cell = alloc['_id'].rsplit('/', 1)
        alloc['name'] = name
        filtered.append(alloc)

    zkutils.put(zkclient, z.path.allocation(), filtered, check_content=True)


def _run_sync():
    """Sync Zookeeper with LDAP, runs with lock held."""
    def match_appgroup(name, group):
        """Match if appgroup belongs to the cell."""
        if context.GLOBAL.cell in group.get('cells', []):
            return name
        else:
            return None

    while True:
        # Sync app groups
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        app_groups = admin_app_group.list({})
        _sync_collection(context.GLOBAL.zk.conn,
                         app_groups, z.path.appgroup(), match_appgroup)

        # Sync allocations.
        admin_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)

        allocations = admin_alloc.list({'cell': context.GLOBAL.cell})
        _sync_allocations(context.GLOBAL.zk.conn,
                          allocations)

        # Servers - because they can have custom topology - are loaded
        # from the plugin.
        try:
            servers_plugin = importlib.import_module(
                'treadmill.plugins.sproc.servers')
            servers_plugin.init()
        except ImportError as err:
            _LOGGER.warn('Unable to load treadmill.plugins.sproc.servers: '
                         '%s', err)

        time.sleep(60)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def top(no_lock):
        """Sync LDAP data with Zookeeper data."""
        context.GLOBAL.zk.conn.ensure_path('/cellsync-election')
        me = '%s.%d' % (sysinfo.hostname(), os.getpid())
        lock = context.GLOBAL.zk.conn.Lock('/cellsync-election', me)
        if not no_lock:
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _run_sync()
        else:
            _LOGGER.info('Running without lock.')
            _run_sync()

    return top
