"""Syncronizes cell Zookeeper with LDAP data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import admin
from treadmill import context
from treadmill.scheduler import master


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

        master.create_bucket(context.GLOBAL.zk.conn, building, None)
        master.cell_insert_bucket(context.GLOBAL.zk.conn, building)
        master.create_bucket(context.GLOBAL.zk.conn, rack, building)
        master.create_server(context.GLOBAL.zk.conn, servername, rack)
        master.update_server_attrs(context.GLOBAL.zk.conn, servername,
                                   traits=traits, partition=partition)


def init():
    """Return top level command handler."""
    return sync_servers()
