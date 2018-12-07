"""Checkout Zookeeper ensemble.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import context
from treadmill import zkadmin


METADATA = {
    'index': 'instance',
    'query': 'select * from zk',
    'checks': [
        {
            'description': 'Ensemble state',
            'query': 'select instance, ok from zk where ok != 1',
            'metric': 'select count(*) as down from ({query})',
            'alerts': [
                {
                    'description': 'All servers are up',
                    'severity': 'error',
                    'threshold':
                    {
                        'down': 1
                    }
                },
                {
                    'description': 'Ensemble has quorum',
                    'severity': 'critical',
                    'threshold':
                    {
                        'down': 2
                    }
                },
            ]
        }
    ]
}


def init():
    """Top level command handler."""

    @click.command('zk')
    def check_zk():
        """Check Zookeeper status."""

        def _check(conn, **_kwargs):
            """Zookeeper state."""
            admin_cell = context.GLOBAL.admin.cell()
            cell = admin_cell.get(context.GLOBAL.cell)

            conn.execute(
                """
                CREATE TABLE zk (
                    instance text,
                    ok integer
                )
                """
            )

            rows = []
            for idx, master in enumerate(cell['masters']):
                host = master['hostname']
                port = master['zk-client-port']
                zkok = zkadmin.ok(host, port)
                rows.append(('{}:{}'.format(host, port), zkok,))

            conn.executemany(
                'INSERT INTO zk(instance, ok) values(?, ?)',
                rows
            )

            return METADATA

        return _check

    return check_zk
