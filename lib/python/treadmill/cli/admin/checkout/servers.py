"""Checkout Zookeeper ensemble.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import context
from treadmill import checkout
from treadmill import zknamespace as z


def _metadata():
    """Returns check metadata."""
    _meta = {
        'index': 'name',
        'query': 'select * from servers order by partition',
        'checks': [
            {
                'description': 'Partitions capacity.',
                'query':
                    """
                    select name, partition, presence from servers
                    where presence != 1
                    order by partition
                    """,
                'metric':
                    """
                    select partition, count(*) as down
                    from ({query})
                    group by partition
                """,
                'alerts': [],
            },
            {
                'description': 'Topology syncronised.',
                'query':
                    """
                    select name, partition, in_zk, in_ldap from servers
                    where in_zk == 0 or in_ldap == 0
                    order by partition
                    """,
                'metric':
                    """
                    select count(*) as not_synced
                    from ({query})
                    group by partition
                """,
                'alerts': [
                    {
                        'description': 'Servers synced between LDAP and Zk',
                        'severity': 'error',
                        'threshold':
                        {
                            'not_synced': 0
                        }
                    },
                ]
            }
        ]
    }

    admin_cell = context.GLOBAL.admin.cell()
    cell = admin_cell.get(context.GLOBAL.cell)

    partitions = cell.get('partitions', [{'_id': '_default'}])
    has_default = False
    for partition in partitions:
        name = partition['_id']
        down_threshold = partition.get('down-threshold', 0)
        if name == '_default':
            has_default = True

        _meta['checks'][0]['alerts'].append({
            'description': 'Partition: {partition}',
            'severity': 'error',
            'match':
            {
                'partition': name,
            },
            'threshold':
            {
                'down': down_threshold,
            }
        })

    if not has_default:
        _meta['checks'][0]['alerts'].append({
            'description': 'Partition: {partition}',
            'severity': 'error',
            'match':
            {
                'partition': '_default'
            },
            'threshold':
            {
                'down': 0,
            }
        })

    return _meta


def init():
    """Top level command handler."""

    @click.command('servers')
    def check_servers():
        """Check Zookeeper status."""

        def _check(conn, **_kwargs):
            """Server state: """
            admin_srv = context.GLOBAL.admin.server()
            servers_in_ldap = {
                server['_id']: server['partition']
                for server in admin_srv.list({'cell': context.GLOBAL.cell})
            }

            zkclient = context.GLOBAL.zk.conn
            presence = set(zkclient.get_children(z.SERVER_PRESENCE))
            in_zk = set(zkclient.get_children(z.SERVERS))
            blacked_out = set(zkclient.get_children(z.BLACKEDOUT_SERVERS))

            conn.execute(
                """
                CREATE TABLE servers (
                    name text,
                    partition text,
                    in_ldap,
                    in_zk,
                    up integer,
                    blackout integer,
                    presence integer
                )
                """
            )

            all_servers = set(servers_in_ldap.keys()) | in_zk
            up = {
                server: checkout.telnet(server)
                for server in all_servers
            }

            rows = []
            for name in set(servers_in_ldap.keys()) | in_zk:
                rows.append((
                    name,
                    servers_in_ldap.get(name),
                    name in servers_in_ldap,
                    name in in_zk,
                    name in up,
                    name in blacked_out,
                    name in presence,
                ))

            conn.executemany(
                """
                INSERT INTO servers(
                    name,
                    partition,
                    in_ldap,
                    in_zk,
                    up,
                    blackout,
                    presence
                ) values(?, ?, ?, ?, ?, ?, ?)
                """, rows
            )

            return _metadata()

        return _check

    return check_servers
