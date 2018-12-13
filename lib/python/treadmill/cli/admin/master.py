"""Implementation of treadmill admin master CLI plugin.
"""

from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import io

import click

from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml
from treadmill.scheduler import masterapi


def server_group(parent):
    """Server CLI group"""
    formatter = cli.make_formatter('server-node')

    @parent.group()
    def server():
        """Manage server configuration.
        """

    @server.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List servers"""
        servers = []
        for name in masterapi.list_servers(context.GLOBAL.zk.conn):
            server = masterapi.get_server(context.GLOBAL.zk.conn,
                                          name,
                                          placement=True)
            server['name'] = name
            servers.append(server)

        cli.out(formatter(servers))

    @server.command()
    @click.option('-f', '--features', help='Server features, - to reset.',
                  multiple=True, default=[])
    @click.option('-p', '--parent', help='Server parent / separated.')
    @click.option('-P', '--partition', help='Server partition.',
                  default='_default')
    @click.option('-m', '--memory', help='Server memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='Server cpu, %.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Server disk.',
                  callback=cli.validate_disk)
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def configure(server, features, parent, partition, memory, cpu, disk):
        """Create, get or modify server configuration"""
        if parent:
            path = parent.split('/')
            bucket = None
            for bucket, bucket_parent in zip(path, [None] + path[:-1]):
                masterapi.create_bucket(
                    context.GLOBAL.zk.conn,
                    bucket,
                    bucket_parent
                )
            assert bucket is not None, 'server topology missing.'

            masterapi.create_server(context.GLOBAL.zk.conn,
                                    server, bucket,
                                    partition=partition)

        features = cli.combine(features)
        if features:
            # This is special case - reset features to empty.
            if features == ['-']:
                features = []

            masterapi.update_server_features(context.GLOBAL.zk.conn,
                                             server, features)

        if memory or cpu or disk:
            masterapi.update_server_capacity(context.GLOBAL.zk.conn, server,
                                             memory=memory,
                                             cpu=cpu,
                                             disk=disk)

        server_obj = masterapi.get_server(context.GLOBAL.zk.conn, server)
        server_obj['name'] = server

        cli.out(formatter(server_obj))

    @server.command()
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def delete(server):
        """Delete server configuration"""
        masterapi.delete_server(context.GLOBAL.zk.conn, server)

    @server.command()
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def reboot(server):
        """Trigger server reboot."""
        masterapi.reboot_server(context.GLOBAL.zk.conn, server)

    @server.command()
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def up(server):  # pylint: disable=C0103
        """Mark server up."""
        masterapi.update_server_state(context.GLOBAL.zk.conn, server, 'up')

    @server.command()
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def down(server):
        """Mark server down."""
        masterapi.update_server_state(context.GLOBAL.zk.conn, server, 'down')

    @server.command()
    @click.option('-u', '--unschedule', type=cli.LIST,
                  help='List of apps to unschedule.')
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def freeze(unschedule, server):
        """Freeze server, optionally unscheduling apps."""
        masterapi.update_server_state(
            context.GLOBAL.zk.conn,
            server,
            'frozen',
            unschedule
        )

    del configure
    del list
    del delete
    del reboot
    del freeze
    del down
    del up


def app_group(parent):
    """App CLI group"""
    formatter = cli.make_formatter('app')

    @parent.group(name='app')
    def app():
        """Manage app configuration.
        """

    @app.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List apps"""
        for appname in masterapi.list_scheduled_apps(context.GLOBAL.zk.conn):
            print(appname)

    @app.command()
    @click.option('-m', '--manifest',
                  type=click.Path(exists=True, readable=True), required=True)
    @click.option('--env', help='Proid environment.', required=True,
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']))
    @click.option('--proid', help='Proid.', required=True)
    @click.option('-n', '--count', type=int, default=1)
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def schedule(app, manifest, count, env, proid):
        """Schedule app(s) on the cell master"""
        with io.open(manifest, 'rb') as fd:
            data = yaml.load(stream=fd)
        # TODO: should we delete all potential attributes starting
        #                with _ ?
        if '_id' in data:
            del data['_id']

        data['environment'] = env
        if 'affinity' not in data:
            # TODO: allow custom affinity formats.
            data['affinity'] = '{0}.{1}'.format(*app.split('.'))

        data['proid'] = proid
        scheduled = masterapi.create_apps(context.GLOBAL.zk.conn,
                                          app, data, count, 'admin')
        for app_id in scheduled:
            print(app_id)

    @app.command()
    @click.argument('instance')
    @cli.admin.ON_EXCEPTIONS
    def configure(instance):
        """View app instance configuration"""
        scheduled = masterapi.get_app(context.GLOBAL.zk.conn, instance)
        cli.out(formatter(scheduled))

    @app.command()
    @click.argument('apps', nargs=-1)
    @cli.admin.ON_EXCEPTIONS
    def delete(apps):
        """Deletes (unschedules) the app by pattern"""
        masterapi.delete_apps(context.GLOBAL.zk.conn, apps, 'admin')

    del list
    del schedule
    del delete
    del configure


def monitor_group(parent):
    """App monitor CLI group"""
    formatter = cli.make_formatter('app-monitor')

    @parent.group()
    def monitor():
        """Manage app monitors configuration.
        """

    @monitor.command()
    @click.option('-n', '--count', type=int, help='Instance count')
    @click.option('-p', '--policy', type=click.Choice(['fifo', 'lifo']),
                  help='Instance scale policy: fifo (remove oldest first), '
                       'lifo (remove newest first)')
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def configure(app, count, policy):
        """Create, get or modify an app monitor configuration"""
        zkclient = context.GLOBAL.zk.conn

        options = {}
        if count is not None:
            options['count'] = count
        if policy is not None:
            options['policy'] = policy

        existing = masterapi.get_appmonitor(zkclient, app)

        # reconfigure if any of the parameters is specified
        if options:
            if count is None and existing is not None:
                count = existing.get('count')
            if policy is None and existing is not None:
                policy = existing.get('policy')
            data = masterapi.update_appmonitor(zkclient, app, count, policy)

        else:
            data = existing

        cli.out(formatter(data))

    @monitor.command()
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def delete(app):
        """Deletes app monitor"""
        masterapi.delete_appmonitor(context.GLOBAL.zk.conn, app)

    @monitor.command(name='list')
    def _list():
        """List all configured monitors"""
        zkclient = context.GLOBAL.zk.conn

        suspended_monitors = masterapi.get_suspended_appmonitors(zkclient)

        monitors = [
            masterapi.get_appmonitor(
                zkclient, app,
                suspended_monitors=suspended_monitors,
            )
            for app in masterapi.appmonitors(zkclient)
        ]

        cli.out(formatter(monitors))

    del delete
    del configure
    del _list


def cell_group(parent):
    """Cell CLI group"""

    @parent.group()
    def cell():
        """Manage top level cell configuration.
        """

    @cell.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def insert(bucket):
        """Add top level bucket to the cell"""
        masterapi.cell_insert_bucket(context.GLOBAL.zk.conn, bucket)

    @cell.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def remove(bucket):
        """Remove top level bucket to the cell"""
        masterapi.cell_remove_bucket(context.GLOBAL.zk.conn, bucket)

    @cell.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List top level bucket in the cell"""
        buckets = masterapi.cell_buckets(context.GLOBAL.zk.conn)
        for bucket in buckets:
            print(bucket)

    del list
    del insert
    del remove


def bucket_group(parent):
    """Bucket CLI group"""
    formatter = cli.make_formatter('bucket')

    @parent.group()
    def bucket():
        """Manage Treadmill bucket configuration.
        """

    @bucket.command()
    @click.option('-f', '--features', help='Bucket features, - to reset',
                  multiple=True, default=[])
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def configure(features, bucket):
        """Create, get or modify bucket configuration"""
        features = cli.combine(features)
        if features:
            # This is special case - reset features to empty.
            if features == ['-']:
                features = None
            masterapi.update_bucket_features(context.GLOBAL.zk.conn,
                                             bucket, features)

        data = masterapi.get_bucket(context.GLOBAL.zk.conn, bucket)
        data['name'] = bucket

        cli.out(formatter(data))

    @bucket.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """Delete bucket"""
        buckets = []
        for name in masterapi.cell_buckets(context.GLOBAL.zk.conn):
            bucket = masterapi.get_bucket(context.GLOBAL.zk.conn, name)
            bucket['name'] = name
            buckets.append(bucket)

        cli.out(formatter(buckets))

    @bucket.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def delete(bucket):
        """Delete bucket"""
        masterapi.delete_bucket(context.GLOBAL.zk.conn, bucket)

    del configure
    del list
    del delete


def identity_group_group(parent):
    """App monitor CLI group"""
    formatter = cli.make_formatter('identity-group')

    @parent.group(name='identity-group')
    def identity_group():
        """Manage identity group configuration.
        """

    @identity_group.command()
    @click.option('-n', '--count', type=int)
    @click.argument('group')
    @cli.admin.ON_EXCEPTIONS
    def configure(group, count):
        """Create, get or modify identity group configuration"""
        zkclient = context.GLOBAL.zk.conn
        if count is not None:
            masterapi.update_identity_group(zkclient, group, count)

        cli.out(formatter(masterapi.get_identity_group(zkclient, group)))

    @identity_group.command()
    @click.argument('group')
    @cli.admin.ON_EXCEPTIONS
    def delete(group):
        """Deletes identity group"""
        masterapi.delete_identity_group(context.GLOBAL.zk.conn, group)

    @identity_group.command(name='list')
    def _list():
        """List all configured identity groups"""
        zkclient = context.GLOBAL.zk.conn
        groups = [
            masterapi.get_identity_group(zkclient, group)
            for group in masterapi.identity_groups(zkclient)
        ]

        cli.out(formatter(groups))

    del delete
    del configure
    del _list


def init():
    """Return top level command handler"""

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def master_group():
        """Manage Treadmill master data.
        """

    cell_group(master_group)
    bucket_group(master_group)
    server_group(master_group)
    app_group(master_group)
    monitor_group(master_group)
    identity_group_group(master_group)

    return master_group
