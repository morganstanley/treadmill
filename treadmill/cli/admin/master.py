"""Implementation of treadmill admin master CLI plugin"""


import click
import yaml

from treadmill import cli
from treadmill import context
from treadmill import master


def server_group(parent):
    """Server CLI group"""
    formatter = cli.make_formatter(cli.ServerNodePrettyFormatter)

    @parent.group()
    def server():
        """Manage server configuration"""
        pass

    @server.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List servers"""
        servers = []
        for name in master.list_servers(context.GLOBAL.zk.conn):
            server = master.get_server(context.GLOBAL.zk.conn, name)
            server['name'] = name
            servers.append(server)

        cli.out(formatter(servers))

    @server.command()
    @click.option('-f', '--features', help='Server features, - to reset.',
                  multiple=True, default=[])
    @click.option('-p', '--parent', help='Server parent / separated.')
    @click.option('-m', '--memory', help='Server memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='Server cpu, %.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Server disk.',
                  callback=cli.validate_disk)
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def configure(server, features, parent, memory, cpu, disk):
        """Create, get or modify server configuration"""
        if parent:
            path = parent.split('/')
            bucket = None
            for bucket, parent in zip(path, [None] + path[:-1]):
                master.create_bucket(context.GLOBAL.zk.conn, bucket, parent)
            assert bucket is not None, 'server topology missing.'

            master.create_server(context.GLOBAL.zk.conn, server, bucket)

        features = cli.combine(features)
        if features:
            # This is special case - reset features to empty.
            if features == ['-']:
                features = []

            master.update_server_features(context.GLOBAL.zk.conn,
                                          server, features)

        if memory or cpu or disk:
            master.update_server_capacity(context.GLOBAL.zk.conn, server,
                                          memory=memory,
                                          cpu=cpu,
                                          disk=disk)

        server_obj = master.get_server(context.GLOBAL.zk.conn, server)
        server_obj['name'] = server

        cli.out(formatter(server_obj))

    @server.command()
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def delete(server):
        """Delete server configuration"""
        master.delete_server(context.GLOBAL.zk.conn, server)

    del configure
    del list
    del delete


def app_group(parent):
    """App CLI group"""
    formatter = cli.make_formatter(cli.AppPrettyFormatter)

    @parent.group(name='app')
    def app():
        """Manage app configuration"""
        pass

    @app.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List apps"""
        for appname in master.list_scheduled_apps(context.GLOBAL.zk.conn):
            print(appname)

    @app.command()
    @click.option('-m', '--manifest', type=click.File('rb'), required=True)
    @click.option('--env', help='Proid environment.', required=True,
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']))
    @click.option('--proid', help='Proid.', required=True)
    @click.option('-n', '--count', type=int, default=1)
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def schedule(app, manifest, count, env, proid):
        """Schedule app(s) on the cell master"""
        data = yaml.load(manifest.read())
        # TODO: should we delete all potential attributes starting
        #                with _ ?
        if '_id' in data:
            del data['_id']

        data['environment'] = env
        if 'affinity' not in data:
            # TODO: allow custom affinity formats.
            data['affinity'] = '{0}.{1}'.format(*app.split('.'))

        data['proid'] = proid
        scheduled = master.create_apps(context.GLOBAL.zk.conn,
                                       app, data, count)
        for app_id in scheduled:
            print(app_id)

    @app.command()
    @click.argument('instance')
    @cli.admin.ON_EXCEPTIONS
    def configure(instance):
        """View app instance configuration"""
        scheduled = master.get_app(context.GLOBAL.zk.conn, instance)
        cli.out(formatter(scheduled))

    @app.command()
    @click.argument('apps', nargs=-1)
    @cli.admin.ON_EXCEPTIONS
    def delete(apps):
        """Deletes (unschedules) the app by pattern"""
        master.delete_apps(context.GLOBAL.zk.conn, apps)

    del list
    del schedule
    del delete
    del configure


def monitor_group(parent):
    """App monitor CLI group"""
    formatter = cli.make_formatter(cli.AppMonitorPrettyFormatter())

    @parent.group()
    def monitor():
        """Manage app monitors configuration"""
        pass

    @monitor.command()
    @click.option('-n', '--count', type=int)
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def configure(app, count):
        """Create, get or modify an app monitor configuration"""
        zkclient = context.GLOBAL.zk.conn
        if count is not None:
            master.update_appmonitor(zkclient, app, count)

        cli.out(formatter(master.get_appmonitor(zkclient, app)))

    @monitor.command()
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def delete(app):
        """Deletes app monitor"""
        master.delete_appmonitor(context.GLOBAL.zk.conn, app)

    @monitor.command(name='list')
    def _list():
        """List all configured monitors"""
        zkclient = context.GLOBAL.zk.conn
        monitors = [
            master.get_appmonitor(zkclient, app)
            for app in master.appmonitors(zkclient)
        ]

        cli.out(formatter(monitors))

    del delete
    del configure
    del _list


def cell_group(parent):
    """Cell CLI group"""

    @parent.group()
    def cell():
        """Manage top level cell configuration"""
        pass

    @cell.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def insert(bucket):
        """Add top level bucket to the cell"""
        master.cell_insert_bucket(context.GLOBAL.zk.conn, bucket)

    @cell.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def remove(bucket):
        """Remove top level bucket to the cell"""
        master.cell_remove_bucket(context.GLOBAL.zk.conn, bucket)

    @cell.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """List top level bucket in the cell"""
        buckets = master.cell_buckets(context.GLOBAL.zk.conn)
        for bucket in buckets:
            print(bucket)

    del list
    del insert
    del remove


def bucket_group(parent):
    """Bucket CLI group"""
    formatter = cli.make_formatter(cli.BucketPrettyFormatter)

    @parent.group()
    def bucket():
        """Manage Treadmill bucket configuration"""
        pass

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
            master.update_bucket_features(context.GLOBAL.zk.conn,
                                          bucket, features)

        data = master.get_bucket(context.GLOBAL.zk.conn, bucket)
        data['name'] = bucket

        cli.out(formatter(data))

    @bucket.command()
    @cli.admin.ON_EXCEPTIONS
    def list():  # pylint: disable=W0622
        """Delete bucket"""
        buckets = []
        for name in master.cell_buckets(context.GLOBAL.zk.conn):
            bucket = master.get_bucket(context.GLOBAL.zk.conn, name)
            bucket['name'] = name
            buckets.append(bucket)

        cli.out(formatter(buckets))

    @bucket.command()
    @click.argument('bucket')
    @cli.admin.ON_EXCEPTIONS
    def delete(bucket):
        """Delete bucket"""
        master.delete_bucket(context.GLOBAL.zk.conn, bucket)

    del configure
    del list
    del delete


def identity_group_group(parent):
    """App monitor CLI group"""
    formatter = cli.make_formatter(cli.IdentityGroupPrettyFormatter)

    @parent.group(name='identity-group')
    def identity_group():
        """Manage identity group configuration"""
        pass

    @identity_group.command()
    @click.option('-n', '--count', type=int)
    @click.argument('group')
    @cli.admin.ON_EXCEPTIONS
    def configure(group, count):
        """Create, get or modify identity group configuration"""
        zkclient = context.GLOBAL.zk.conn
        if count is not None:
            master.update_identity_group(zkclient, group, count)

        cli.out(formatter(master.get_identity_group(zkclient, group)))

    @identity_group.command()
    @click.argument('group')
    @cli.admin.ON_EXCEPTIONS
    def delete(group):
        """Deletes identity group"""
        master.delete_identity_group(context.GLOBAL.zk.conn, group)

    @identity_group.command(name='list')
    def _list():
        """List all configured identity groups"""
        zkclient = context.GLOBAL.zk.conn
        groups = [
            master.get_identity_group(zkclient, group)
            for group in master.identity_groups(zkclient)
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
    def master_group():
        """Manage Treadmill master data"""
        pass

    cell_group(master_group)
    bucket_group(master_group)
    server_group(master_group)
    app_group(master_group)
    monitor_group(master_group)
    identity_group_group(master_group)

    return master_group
