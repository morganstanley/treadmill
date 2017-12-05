"""Syncronizes cell Zookeeper with LDAP data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import importlib
import logging
import time

import click

from treadmill import admin
from treadmill import context
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.scheduler import masterapi

_LOGGER = logging.getLogger(__name__)


def _match_appgroup(group):
    """Match if appgroup belongs to the cell.
    """
    return context.GLOBAL.cell in group.get('cells', [])


def _sync_collection(zkclient, entities, zkpath, match=None):
    """Sync ldap collection to Zookeeper.
    """
    _LOGGER.info('Sync: %s', zkpath)
    zkclient.ensure_path(zkpath)

    in_zk = zkclient.get_children(zkpath)

    to_sync = {}
    for entity in entities:
        name = entity.pop('_id')
        if match and not match(entity):
            _LOGGER.debug('Skip: %s', name)
            continue
        to_sync[name] = entity

    for to_del in set(in_zk) - set(to_sync):
        _LOGGER.info('Delete: %s', to_del)
        zkutils.ensure_deleted(zkclient, z.join_zookeeper_path(zkpath, to_del))

    # Add or update current app-groups
    for name, entity in to_sync.items():
        if zkutils.put(zkclient, z.join_zookeeper_path(zkpath, name),
                       entity, check_content=True):
            _LOGGER.info('Update: %s', name)
        else:
            _LOGGER.info('Up to date: %s', name)


def _sync_partitions(zkclient, entities):
    """Syncs partitions to Zookeeper.
    """
    _LOGGER.info('Sync: %s', z.path.partition())

    zkclient.ensure_path(z.path.partition())

    in_zk = zkclient.get_children(z.path.partition())
    names = [entity['_id'] for entity in entities]

    for extra in set(in_zk) - set(names):
        _LOGGER.debug('Delete: %s', extra)
        zkutils.ensure_deleted(zkclient, z.path.partition(extra))

    # Add or update current partitions
    for entity in entities:
        zkname = entity['_id']

        if 'reboot-schedule' in entity:
            try:
                entity['reboot-schedule'] = utils.reboot_schedule(
                    entity['reboot-schedule']
                )
            except ValueError:
                _LOGGER.info('Invalid reboot schedule, ignoring.')

        if zkutils.put(zkclient, z.path.partition(zkname),
                       entity, check_content=True):
            _LOGGER.info('Update: %s', zkname)
        else:
            _LOGGER.info('Up to date: %s', zkname)


def _sync_allocations(zkclient, allocations):
    """Syncronize allocations.
    """
    filtered = []
    for alloc in allocations:
        _LOGGER.info('Sync allocation: %s', alloc)
        name, _cell = alloc['_id'].rsplit('/', 1)
        alloc['name'] = name
        filtered.append(alloc)
    masterapi.update_allocations(zkclient, filtered)


def _run_sync():
    """Sync Zookeeper with LDAP, runs with lock held.
    """
    while True:
        # Sync app groups
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        app_groups = admin_app_group.list({})
        _sync_collection(context.GLOBAL.zk.conn,
                         app_groups, z.path.appgroup(), _match_appgroup)

        # Sync partitions
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        partitions = admin_cell.partitions(context.GLOBAL.cell)
        _sync_partitions(context.GLOBAL.zk.conn, partitions)

        # Sync allocations.
        admin_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)

        allocations = admin_alloc.list({'cell': context.GLOBAL.cell})
        _sync_allocations(context.GLOBAL.zk.conn,
                          allocations)

        # Global servers
        admin_srv = admin.Server(context.GLOBAL.ldap.conn)
        global_servers = admin_srv.list({})
        zkutils.ensure_exists(
            context.GLOBAL.zk.conn,
            z.path.globals('servers'),
            data=[server['_id'] for server in global_servers]
        )

        # Servers - because they can have custom topology - are loaded
        # from the plugin.
        try:
            servers_plugin = importlib.import_module(
                'treadmill.ms.plugins.sproc.servers')
            servers_plugin.init()
        except ImportError as err:
            _LOGGER.warning(
                'Unable to load treadmill.ms.plugins.sproc.servers: %s',
                err
            )

        time.sleep(60)


def init():
    """Return top level command handler.
    """

    @click.command()
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def top(no_lock):
        """Sync LDAP data with Zookeeper data.
        """
        if not no_lock:
            _LOGGER.info('Waiting for leader lock.')
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            with lock:
                _run_sync()
        else:
            _LOGGER.info('Running without lock.')
            _run_sync()

    return top
