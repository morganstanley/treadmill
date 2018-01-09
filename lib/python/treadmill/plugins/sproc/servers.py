"""Syncronizes cell Zookeeper with LDAP data.
"""

# pylint: disable=E0611
from treadmill import admin
from treadmill import context
from treadmill.scheduler import masterapi


def sync_servers():
    """Sync servers and buckets."""
    admin_srv = admin.Server(context.GLOBAL.ldap.conn)
    servers = admin_srv.list({'cell': context.GLOBAL.cell})

    for server in servers:
        servername = server['_id']

        rack = 'rack:unknown'
        building = 'building:unknown'

        traits = []
        partition = None

        masterapi.create_bucket(context.GLOBAL.zk.conn, building, None)
        masterapi.cell_insert_bucket(context.GLOBAL.zk.conn, building)
        masterapi.create_bucket(context.GLOBAL.zk.conn, rack, building)
        masterapi.create_server(context.GLOBAL.zk.conn, servername, rack)
        masterapi.update_server_attrs(context.GLOBAL.zk.conn, servername,
                                      traits=traits, partition=partition)


def init():
    """Return top level command handler."""
    return sync_servers()
