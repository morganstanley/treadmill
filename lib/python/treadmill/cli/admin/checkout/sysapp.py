"""Checkout cell sysapps
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
import kazoo

from treadmill import cli
from treadmill import checkout
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

_APPS = ['app-dns', 'cellapi', 'adminapi', 'stateapi', 'wsapi']


def _metadata(apps):
    _meta = {
        'index': 'app',
        'query': 'select * from sysapps',
        'checks': [
            {
                'description': 'Sysapp state',
                'query':
                    """
                    select app, instance, health from sysapp_instance
                    order by app
                    """,
                'metric': 'select app, (expect - count) as down from sysapp',
                'alerts': []
            }
        ]
    }

    for (app, count) in _sysapp_expect_count(apps):
        # check if #sysapp is correct (error) and #sysapp is zero (critical)
        _meta['checks'][0]['alerts'].append({
            'description': '{app} is healthy',
            'severity': 'error',
            'match': {
                'app': app,
            },
            'threshold': {
                'down': 1
            }
        })
        _meta['checks'][0]['alerts'].append({
            'description': '{app} is functioning',
            'severity': 'error',
            'match': {
                'app': app,
            },
            'threshold': {
                'down': count,
            }
        })

    return _meta


def _get_cell_proid():
    """get cell name ane sys proid
    """
    admin_cell = context.GLOBAL.admin.cell()
    cell = admin_cell.get(context.GLOBAL.cell)
    return cell['username']


def _get_appmonitor(app):
    """get appmonitor count from appname
    """
    zkclient = context.GLOBAL.zk.conn
    data = zkutils.get(zkclient, z.path.appmonitor(app))

    return data['count']


def _get_identity_group(app):
    """get identity group if exists
    """
    zkclient = context.GLOBAL.zk.conn
    data = zkutils.get(zkclient, z.path.identity_group(app))

    return data['count']


def _get_endpoints(proid):
    """get all endpoints of a proid
    """
    zkclient = context.GLOBAL.zk.conn
    endpoint_path = z.join_zookeeper_path(z.ENDPOINTS, proid)
    return zkclient.get_children(endpoint_path)


def _sysapp_expect_count(apps):
    """yield all sysapp app monitors
    """
    sysproid = _get_cell_proid()
    cell_name = context.GLOBAL.cell

    for app in apps:
        app = '{}.{}.{}'.format(sysproid, app, cell_name)
        count = _get_appmonitor(app)
        try:
            # FIXME: at the moment, we suppose identity group name same as app
            identity_count = _get_identity_group(app)
            if identity_count < count:
                count = identity_count
        except kazoo.client.NoNodeError:
            pass  # we do not care if identity_group does not exist

        yield (app, count)


def _instance_healthy(instance, endpoints):
    """helper to see if instance is healthy (connectable)
    """
    (proid, instance_name) = instance.split('.', 1)
    instance_endpoints = [
        val for val in endpoints
        if val.startswith(instance_name)
    ]

    zkclient = context.GLOBAL.zk.conn
    for endpoint in instance_endpoints:
        fullpath = z.join_zookeeper_path(z.ENDPOINTS, proid, endpoint)
        hostport, _metadata = zkclient.get(fullpath)
        (host, port) = hostport.decode().split(':')
        if not checkout.connect(host, port):
            return False

    return True


def init():
    """Top level command handler."""

    @click.command('sysapp')
    @click.option('--apps', help='apps to check', type=cli.LIST)
    def check_sysapp(apps):
        """Check sysapps status."""
        if not apps:
            apps = _APPS

        def _check(conn, **_kwargs):
            """Sysapp state."""
            cell_name = context.GLOBAL.cell
            sysproid = _get_cell_proid()
            # get all running containers started by treadmill proid
            zkclient = context.GLOBAL.zk.conn
            runnings = zkclient.get_children(z.RUNNING)
            # prefilter treadmill apps to improve efficiency
            runnings = [val for val in runnings if val.startswith(sysproid)]
            endpoints = _get_endpoints(sysproid)

            conn.execute(
                """
                CREATE TABLE sysapp (
                    app text,
                    expect integer,
                    count integer
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE sysapp_instance (
                    app text,
                    instance text,
                    health integer
                )
                """
            )

            # we get each running instance of expected app
            # if the instance endpoint is connectable, we regard it as good
            apps_data = {}
            rows = []
            for (app, count) in _sysapp_expect_count(apps):
                _LOGGER.debug('Expect: %s => %d', app, count)
                apps_data[app] = [count, 0]
                for running in runnings:
                    if app in running:
                        healthy = _instance_healthy(running, endpoints)
                        _LOGGER.debug(
                            'checking %s, healthy: %r', running, healthy
                        )

                        if healthy:
                            apps_data[app][1] += 1

                        rows.append((app, running, healthy))

            conn.executemany(
                """
                INSERT INTO sysapp_instance
                    (app, instance, health)
                VALUES
                    (?, ?, ?)
                """,
                rows
            )

            conn.executemany(
                'INSERT INTO sysapp (app, expect, count) VALUES (?, ?, ?)',
                [(app, val[0], val[1]) for (app, val) in apps_data.items()]
            )
            return _metadata(apps)

        return _check

    return check_sysapp
