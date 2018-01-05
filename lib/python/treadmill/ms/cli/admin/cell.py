"""Admin Cell CLI module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys
import time

import click
import jinja2
from ldap3.core import exceptions as ldap_exceptions
import six

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml
from treadmill import zkadmin
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.api import instance
from treadmill.scheduler import masterapi

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import zapp


_LOGGER = logging.getLogger(__name__)


_CELL_APPS = [
    'adminapi', 'wsapi', 'app-dns', 'stateapi', 'cellapi',
    'lbvirtual', 'lbvirtual-checkout', 'export-reports',
    'app-event', 'prodperim'
]


class CellCtx(object):
    """Cell context."""

    def __init__(self, realm, version):
        self.cell = context.GLOBAL.cell
        self.realm = realm

        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(self.cell)
        location_cells = admin_cell.list({'location': cell['location']})

        self.version = cell['version']
        if version:
            self.version = version
        self.proid = cell['username']
        self.treadmill = cell.get('root')
        self.data = cell.get('data')
        if not self.treadmill:
            self.treadmill = _treadmill_root(self.version)
        self.location = cell['location']
        self.location_cells = [cell['_id'] for cell in location_cells]


def _treadmill_root(version):
    """Returns treadmill root for given version."""
    return '/ms/dist/cloud/PROJ/treadmill/{}/common'.format(version)


def _cell_version(cellname):
    """Gets the cell based treadmill root."""
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    cell = admin_cell.get(cellname)
    version = cell.get('version')

    if version is None:
        raise Exception('Version is not defined for cell: {}'.format(cellname))

    root = cell.get('root')
    if not root:
        root = _treadmill_root(version)

    return version, root


def _zkok(cell):
    """Check that Zookeeper ensemble has two followers and is ok."""
    status = {
        'follower': 0,
        'leader': 0,
    }

    for master in cell['masters']:
        hostname = master['hostname']
        port = master['zk-client-port']
        try:
            zk_status = zkadmin.netcat(hostname, port, 'stat\n')
            for line in zk_status.splitlines():
                line.strip()
                if line == 'Mode: follower':
                    status['follower'] += 1
                    break
                if line == 'Mode: leader':
                    status['leader'] += 1
                    break
        except Exception:  # pylint: disable=W0703
            return False

    return (status['leader'] == 1) and (status['follower'] == 2)


def _display_server_versions(server, data):
    """Display server version data.
    """
    for item in data:
        print('{host:30}   {since:10}   {codepath:60}'.format(
            host=server,
            codepath=item['codepath'],
            since=time.ctime(item['since'])
        ))


def init():
    """Admin Cell CLI module"""

    @click.group(name='cell')
    @click.option('--realm', help='Master kerberos realm',
                  default='is1.morgan')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--version', help='Override the version in LDAP')
    @click.pass_context
    def cell_grp(ctx, realm, version):
        """Manage treadmill cell."""
        ctx.obj = CellCtx(realm, version)

    @cell_grp.command(name='restart-servers')
    @click.pass_context
    def restart_servers(ctx):
        """Restart cell servers."""
        del ctx

    @cell_grp.command(name='restart-masters')
    @click.option('--plant', required=False, help='Zapp plant id')
    @click.pass_context
    def restart_masters(ctx, plant):
        """Restart cell masters."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        if not plant:
            plant = zapp.cell2plant(ctx.obj.cell)

        cell = admin_cell.get(ctx.obj.cell)
        zapp_client = zapp.Zapp(ctx.obj.cell, plant)

        for master in cell['masters']:
            hostname = master['hostname']
            idx = master['idx']

            print('restarting:', hostname, end='')
            zapp_client.restart_master(hostname, idx)
            print('Success.')

    @cell_grp.command(name='clear-blackout')
    @click.option('--plant', required=False, help='Zapp plant id')
    @click.option('--wipe', is_flag=True, default=False)
    @click.pass_context
    def clear_blackout(ctx, plant, wipe):
        """Clear cell blackout."""
        zkclient = context.GLOBAL.zk.conn
        if not plant:
            plant = zapp.cell2plant(ctx.obj.cell)

        zapp_client = zapp.Zapp(ctx.obj.cell, plant)

        blacked_out = zkclient.get_children(z.BLACKEDOUT_SERVERS)
        for server in blacked_out:
            if wipe:
                zapp_client.mark_server_for_wipe(server)

            zapp_client.stop_server(server)
            zkutils.ensure_deleted(zkclient, z.path.blackedout_server(server))
            zapp_client.start_server(server)

    @cell_grp.command(name='configure-apps')
    @click.option('--root', help='Treadmill root override.')
    @click.option('--apps', type=cli.LIST, help='List of apps to configure.')
    @click.option('--dry-run', help='Dry run.', is_flag=True, default=False)
    @click.pass_context
    def configure_apps(ctx, root, apps, dry_run):
        """Configure cell API."""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)

        if not apps:
            apps = _CELL_APPS

        if root:
            ctx.obj.treadmill = root

        jinja_env = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

        # Configure apps identity groups
        template = jinja_env.get_template('identity-groups')
        identity_groups = yaml.load(template.render(**ctx.obj.__dict__))
        for groupname, count in six.iteritems(identity_groups):
            print(groupname, count)
            if not dry_run:
                masterapi.update_identity_group(
                    context.GLOBAL.zk.conn,
                    groupname,
                    count
                )

        # Configure apps
        for appname in apps:
            template = jinja_env.get_template(appname)
            app = yaml.load(template.render(**ctx.obj.__dict__))

            fullname = '{}.{}.{}'.format(ctx.obj.proid, appname, ctx.obj.cell)

            print(fullname)
            print(yaml.dump(app))
            print('...')

            if not dry_run:
                try:
                    admin_app.create(fullname, app)
                except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                    admin_app.replace(fullname, app)

    @cell_grp.command(name='configure-monitors')
    @click.option('--monitors', type=cli.DICT,
                  help='Key/value pairs for monitor count overrides.')
    @click.pass_context
    def configure_monitors(ctx, monitors):
        """Configure system apps monitors."""
        jinja_env = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

        if not monitors:
            template = jinja_env.get_template('monitors')
            monitors = yaml.load(template.render(**ctx.obj.__dict__))

        for name, count in six.iteritems(monitors):
            print(name, count)
            masterapi.update_appmonitor(
                context.GLOBAL.zk.conn,
                name,
                int(count)
            )
        click.echo('Remember to properly configure monitors for lbvirtual.')

    @cell_grp.command(name='configure-appgroups')
    @click.pass_context
    def configure_appgroups(ctx):
        """Configure system app groups."""
        jinja_env = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

        template = jinja_env.get_template('appgroups')
        appgroups = yaml.load(template.render(**ctx.obj.__dict__))

        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        for name, data in six.iteritems(appgroups):
            print(name, data)
            try:
                admin_app_group.create(name, data)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_app_group.update(name, data)

            existing = admin_app_group.get(name)
            group_cells = set(existing['cells'])
            group_cells.update([ctx.obj.cell])
            admin_app_group.update(name, {'cells': list(group_cells)})
            existing = admin_app_group.get(name)
            print(existing)

    @cell_grp.command(name='restart-apps')
    @click.option('--apps', type=cli.LIST,
                  help='List of apps to restart.')
    @click.option('--wait', type=int, help='Interval to wait before re-start.',
                  default=20)
    @click.pass_context
    def restart_apps(ctx, wait, apps):
        """Restart cell API."""
        jinja_env = jinja2.Environment(loader=jinja2.PackageLoader(__name__))

        instance_api = instance.API()
        template = jinja_env.get_template('monitors')
        monitors = yaml.load(template.render(**ctx.obj.__dict__))

        for name, count in six.iteritems(monitors):
            _, appname, _ = name.split('.')
            if apps and appname not in apps:
                continue

            for _idx in range(0, count):
                instance_ids = instance_api.create(name, {}, 1)
                print([str(inst_id) for inst_id in instance_ids], end='')
                for _sec in range(0, wait):
                    print('.', end='')
                    sys.stdout.flush()
                    time.sleep(1)
                print('.')

    @cell_grp.command(name='server-version')
    @click.option('--server', help='Display versions of server.')
    def server_version(server):
        """Display server versions.
        """
        zkclient = context.GLOBAL.zk.conn
        if server:
            data = zkutils.get(zkclient, z.path.version_history(server))
            _display_server_versions(server, data)
        else:
            servers = zkclient.get_children(z.path.version_history())
            for server_ in servers:
                data = zkutils.get(zkclient, z.path.version_history(server_))
                # display only latest version
                _display_server_versions(server_, data[:1])

    del clear_blackout
    del restart_apps
    del configure_apps
    del configure_monitors
    del configure_appgroups
    del restart_masters
    del restart_servers
    del server_version

    return cell_grp
