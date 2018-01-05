"""Syncronizes cell Zookeeper with LDAP data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# TODO: use LDAP persistent search for incremental updates.

import logging
import sqlite3

from treadmill import admin
from treadmill import context
from treadmill.scheduler import masterapi

_LOGGER = logging.getLogger(__name__)

_HOSTDATA_DB = '//ms/dist/aquilon/PROJ/datawarehouse/dumpv3/common/hostdata.db'


def sync_servers():
    """Sync servers and buckets.
    """
    _LOGGER.info('Syncing servers.')

    zkclient = context.GLOBAL.zk.conn
    conn = sqlite3.connect(_HOSTDATA_DB)

    admin_srv = admin.Server(context.GLOBAL.ldap.conn)
    servers = admin_srv.list({'cell': context.GLOBAL.cell})

    for server in servers:
        servername = server['_id']
        _LOGGER.info('Loading %s', servername)

        rack_col, bunker_col, building_col = None, None, None
        try:
            cur = conn.cursor()
            cur.execute(
                'select rack, bunker, building from hosts where hostname=?',
                (servername, )
            )
            rack_col, bunker_col, building_col = cur.fetchone()
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Unable to load server topology: %s', servername)

        rack = 'rack:' + (rack_col or bunker_col or 'unknown')
        building = 'building:' + (building_col or 'unknown')

        traits = server.get('traits', [])
        partition = server.get('partition')
        _LOGGER.info('Update: %s %s %s %r',
                     servername, rack, building, traits)

        masterapi.create_bucket(zkclient, building, None)
        masterapi.cell_insert_bucket(zkclient, building)
        masterapi.create_bucket(zkclient, rack, building)
        masterapi.create_server(zkclient, servername, rack)
        masterapi.update_server_attrs(zkclient, servername,
                                      traits=traits, partition=partition)

    ldap_servers = set(server['_id'] for server in servers)
    zk_servers = set(masterapi.list_servers(zkclient))
    for servername in zk_servers - ldap_servers:
        _LOGGER.info('Delete: %s', servername)
        masterapi.delete_server(zkclient, servername)


def init():
    """Return top level command handler.
    """
    return sync_servers()
