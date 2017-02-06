"""Implementation of treadmill admin ldap CLI plugin."""


import logging

import click
import ldap3
import yaml

from treadmill import admin
from treadmill import cli
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def server_group(parent):
    """Configures server CLI group"""
    formatter = cli.make_formatter(cli.ServerPrettyFormatter)

    @parent.group()
    def server():
        """Manage server configuration"""
        pass

    @server.command()
    @click.option('-c', '--cell', help='Treadmll cell')
    @click.option('-t', '--traits', help='List of server traits',
                  multiple=True, default=[])
    @click.option('-l', '--label', help='Server label')
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def configure(cell, traits, server, label):
        """Create, get or modify server configuration"""
        admin_srv = admin.Server(context.GLOBAL.ldap.conn)

        attrs = {}
        if cell:
            attrs['cell'] = cell
        if traits:
            attrs['traits'] = cli.combine(traits)
        if label:
            if label == '-':
                label = None
            attrs['label'] = label

        if attrs:
            try:
                admin_srv.create(server, attrs)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_srv.update(server, attrs)

        try:
            cli.out(formatter(admin_srv.get(server)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Server does not exist: %s' % server, err=True)

    @server.command(name='list')
    @click.option('-c', '--cell', help='Treadmll cell.')
    @click.option('-t', '--traits', help='List of server traits',
                  multiple=True, default=[])
    @click.option('-l', '--label', help='Server label')
    @cli.admin.ON_EXCEPTIONS
    def _list(cell, traits, label):
        """List servers"""
        admin_srv = admin.Server(context.GLOBAL.ldap.conn)
        servers = admin_srv.list({'cell': cell,
                                  'traits': cli.combine(traits),
                                  'label': label})
        cli.out(formatter(servers))

    @server.command()
    @click.argument('servers', nargs=-1)
    @cli.admin.ON_EXCEPTIONS
    def delete(servers):
        """Delete server(s)"""
        admin_srv = admin.Server(context.GLOBAL.ldap.conn)
        for server in servers:
            admin_srv.delete(server)

    del delete
    del _list
    del configure


def dns_group(parent):  # pylint: disable=R0912
    """Configures Critical DNS CLI group"""
    formatter = cli.make_formatter(cli.DNSPrettyFormatter)

    _default_nameservers = ['localhost']

    @parent.group()
    def dns():
        """Manage Critical DNS server configuration"""
        pass

    @dns.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--server', help='Server name',
                  required=False, type=cli.LIST)
    @click.option('-m', '--manifest', help='Load DNS from manifest file',
                  type=click.File('rb'), required=True)
    @cli.admin.ON_EXCEPTIONS
    def configure(name, server, manifest):
        """Create, get or modify Critical DNS quorum"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)

        data = yaml.load(manifest.read())

        if server is not None:
            data['server'] = server
        if 'nameservers' not in data:
            data['nameservers'] = _default_nameservers

        if not isinstance(data['server'], list):
            data['server'] = data['server'].split(',')
        if not isinstance(data['rest-server'], list):
            data['rest-server'] = data['rest-server'].split(',')

        try:
            admin_dns.create(name, data)
        except ldap3.LDAPEntryAlreadyExistsResult:
            admin_dns.update(name, data)

        try:
            cli.out(formatter(admin_dns.get(name)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Server does not exist: %s' % name, err=True)

    @dns.command(name='list')
    @click.argument('name', nargs=1, required=False)
    @click.option('--server', help='List servers matching this name',
                  required=False)
    @cli.admin.ON_EXCEPTIONS
    def _list(name, server):
        """Displays Critical DNS servers list"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        attrs = {}
        if name is not None:
            attrs['_id'] = name
        if server is not None:
            attrs['server'] = server

        servers = admin_dns.list(attrs)
        cli.out(formatter(servers))

    @dns.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def delete(name):
        """Delete Critical DNS server"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        admin_dns.delete(name)

    del delete
    del _list
    del configure


def app_groups_group(parent):  # pylint: disable=R0912
    """Configures App Groups"""
    formatter = cli.make_formatter(cli.AppGroupPrettyFormatter)

    @parent.group(name='app-group')
    def app_group():  # pylint: disable=W0621
        """Manage App Groups"""
        pass

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--group-type', help='App group type',
                  required=False)
    @click.option('--cell', help='Cell app pattern could be in; comma '
                  'separated list of cells', type=cli.LIST)
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoints',
                  help='App group endpoints, comma separated list.',
                  type=cli.LIST)
    @click.option('--data', help='App group specific data as key=value '
                  'comma separated list', type=cli.LIST)
    def configure(name, group_type, cell, pattern, endpoints, data):
        """Create, get or modify an App Group"""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)

        data_struct = {}
        if group_type:
            data_struct['group-type'] = group_type
        if cell:
            data_struct['cells'] = cell
        if pattern is not None:
            data_struct['pattern'] = pattern
        if data is not None:
            data_struct['data'] = data
        if endpoints is not None:
            data_struct['endpoints'] = endpoints

        if data_struct:
            try:
                admin_app_group.create(name, data_struct)
                _LOGGER.debug('Created app group %s', name)
            except ldap3.LDAPEntryAlreadyExistsResult:
                _LOGGER.debug('Updating app group %s', name)
                admin_app_group.update(name, data_struct)

        try:
            cli.out(formatter(admin_app_group.get(name)))
        except ldap3.LDAPNoSuchObjectResult:
            cli.bad_exit('App group does not exist: %s', name)

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--add', help='Cells to to add.', type=cli.LIST)
    @click.option('--remove', help='Cells to to remove.', type=cli.LIST)
    @cli.admin.ON_EXCEPTIONS
    def cells(add, remove, name):
        """Add or remove cells from the app-group"""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        existing = admin_app_group.get(name)
        group_cells = set(existing['cells'])

        if add:
            group_cells.update(add)
        if remove:
            group_cells = group_cells - set(remove)

        admin_app_group.update(name, {'cells': list(group_cells)})
        cli.out(formatter(admin_app_group.get(name)))

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def get(name):
        """Get an App Group entry"""
        try:
            admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
            cli.out(formatter(admin_app_group.get(name)))
        except ldap3.LDAPNoSuchObjectResult:
            cli.bad_exit('App group does not exist: %s', name)

    @app_group.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List App Group entries"""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        app_group_entries = admin_app_group.list({})
        cli.out(formatter(app_group_entries))

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def delete(name):
        """Delete an App Group entry"""
        admin_app_group = admin.AppGroup(context.GLOBAL.ldap.conn)
        admin_app_group.delete(name)

    del delete
    del _list
    del get
    del cells
    del configure


def app_group(parent):
    """Configures app CLI group"""
    # Disable too many branches.
    #
    # pylint: disable=R0912
    formatter = cli.make_formatter(cli.AppPrettyFormatter)

    @parent.group()
    def app():
        """Manage applications"""
        pass

    @app.command()
    @click.option('-m', '--manifest', help='Application manifest.',
                  type=click.File('rb'))
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def configure(app, manifest):
        """Create, get or modify an app configuration"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        if manifest:
            data = yaml.load(manifest.read())
            try:
                admin_app.create(app, data)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_app.replace(app, data)

        try:
            cli.out(formatter(admin_app.get(app)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    @app.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured applicaitons"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        cli.out(formatter(admin_app.list({})))

    @app.command()
    @click.argument('app')
    @cli.admin.ON_EXCEPTIONS
    def delete(app):
        """Delete applicaiton"""
        admin_app = admin.Application(context.GLOBAL.ldap.conn)
        try:
            admin_app.delete(app)
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('App does not exist: %s' % app, err=True)

    del delete
    del _list
    del configure


def schema_group(parent):
    """Schema CLI group"""

    formatter = cli.make_formatter(cli.LdapSchemaPrettyFormatter)

    @parent.command()
    @click.option('-l', '--load', help='Schema (YAML) file.',
                  type=click.File('rb'))
    @cli.admin.ON_EXCEPTIONS
    def schema(load):
        """View or update LDAP schema"""
        if load:
            schema = yaml.load(load.read())
            context.GLOBAL.ldap.conn.update_schema(schema)

        schema_obj = context.GLOBAL.ldap.conn.schema()

        def dict_to_namevalue_list(item):
            """Translates name: value dict into [{name: $name, ...}]"""
            return [pair[1].update({'name': pair[0]}) or pair[1]
                    for pair in sorted(item.items())]

        schema_obj['attributeTypes'] = dict_to_namevalue_list(
            schema_obj['attributeTypes'])
        schema_obj['objectClasses'] = dict_to_namevalue_list(
            schema_obj['objectClasses'])

        cli.out(formatter(schema_obj))

    del schema


def direct_group(parent):
    """Direct ldap access CLI group"""

    @parent.group()
    def direct():
        """Direct access to LDAP data"""
        pass

    @direct.command()
    @click.option('-c', '--cls', help='Object class', required=True)
    @click.option('-a', '--attrs', help='Addition attributes',
                  type=cli.LIST)
    @click.argument('rec_dn')
    @cli.admin.ON_EXCEPTIONS
    def get(rec_dn, cls, attrs):
        """List all defined DNs"""
        if not attrs:
            attrs = []
        try:
            # TODO: it is porbably possible to derive class from DN.
            klass = getattr(admin, cls)
            attrs.extend([elem[0] for elem in klass.schema()])
        except AttributeError:
            cli.bad_exit('Invalid admin type: %s', cls)
            return

        entry = context.GLOBAL.ldap.conn.get(
            rec_dn, '(objectClass=*)', list(set(attrs)))
        formatter = cli.make_formatter(None)
        cli.out(formatter(entry))

    @direct.command(name='list')
    @click.option('--root', help='Search root.')
    @cli.admin.ON_EXCEPTIONS
    def _list(root):
        """List all defined DNs"""
        dns = context.GLOBAL.ldap.conn.list(root)
        for rec_dn in dns:
            cli.out(rec_dn)

    @direct.command()
    @cli.admin.ON_EXCEPTIONS
    @click.argument('rec_dn', required=True)
    def delete(rec_dn):
        """Delete LDAP object by DN"""
        context.GLOBAL.ldap.conn.delete(rec_dn)

    del get
    del delete

    return direct


def init_group(parent):
    """Init LDAP CLI group"""

    # Disable redeginig name 'init' warning.
    #
    # pylint: disable=W0621
    @parent.command()
    @click.argument('domain')
    @cli.admin.ON_EXCEPTIONS
    def init(domain):
        """Initializes the LDAP directory structure"""
        return context.GLOBAL.ldap.conn.init(domain)

    del init


def cell_group(parent):
    """Configures server CLI group"""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    formatter = cli.make_formatter(cli.CellPrettyFormatter)

    @parent.group()
    @cli.admin.ON_EXCEPTIONS
    def cell():
        """Manage cell configuration"""
        pass

    @cell.command()
    @click.option('-v', '--version', help='Version.')
    @click.option('-r', '--root', help='Distro root.')
    @click.option('-l', '--location', help='Cell location.')
    @click.option('-u', '--username', help='Cell proid account.')
    @click.option('--archive-server', help='Archive server.')
    @click.option('--archive-username', help='Archive username.')
    @click.option('--ssq-namespace', help='SSQ namespace.')
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def configure(cell, version, root, location, username, archive_server,
                  archive_username, ssq_namespace):
        """Create, get or modify cell configuration"""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        attrs = {}
        if version:
            attrs['version'] = version
        if root:
            attrs['root'] = root
        if location:
            attrs['location'] = location
        if username:
            attrs['username'] = username
        if archive_server:
            attrs['archive-server'] = archive_server
        if archive_server:
            attrs['archive-username'] = archive_username
        if ssq_namespace:
            attrs['ssq-namespace'] = ssq_namespace

        if attrs:
            try:
                admin_cell.create(cell, attrs)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_cell.update(cell, attrs)

        try:
            cli.out(formatter(admin_cell.get(cell)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command()
    @click.option('--idx', help='Master index.',
                  type=click.Choice(['1', '2', '3']),
                  required=True)
    @click.option('--hostname', help='Master hostname.',
                  required=True)
    @click.option('--client-port', help='Zookeeper client port.',
                  type=int,
                  required=True)
    @click.option('--kafka-client-port', help='Kafka client port.',
                  type=int,
                  required=False)
    @click.option('--jmx-port', help='Zookeeper jmx port.',
                  type=int,
                  required=True)
    @click.option('--followers-port', help='Zookeeper followers port.',
                  type=int,
                  required=True)
    @click.option('--election-port', help='Zookeeper election port.',
                  type=int,
                  required=True)
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def insert(cell, idx, hostname, client_port, jmx_port, followers_port,
               election_port, kafka_client_port):
        """Add master server to a cell"""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        data = {
            'idx': int(idx),
            'hostname': hostname,
            'zk-client-port': client_port,
            'zk-jmx-port': jmx_port,
            'zk-followers-port': followers_port,
            'zk-election-port': election_port,
        }
        if kafka_client_port is not None:
            data['kafka-client-port'] = kafka_client_port

        attrs = {
            'masters': [data]
        }

        try:
            admin_cell.update(cell, attrs)
            cli.out(formatter(admin_cell.get(cell)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command()
    @click.option('--idx', help='Master index.',
                  type=click.Choice(['1', '2', '3']),
                  required=True)
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def remove(cell, idx):
        """Remove master server from a cell"""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        attrs = {
            'masters': [{
                'idx': int(idx),
                'hostname': None,
                'zk-client-port': None,
                'zk-jmx-port': None,
                'zk-followers-port': None,
                'zk-election-port': None,
            }]
        }

        try:
            admin_cell.remove(cell, attrs)
            cli.out(formatter(admin_cell.get(cell)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """Displays master servers"""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cells = admin_cell.list({})
        cli.out(formatter(cells))

    @cell.command()
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def delete(cell):
        """Delete a cell"""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

        try:
            admin_cell.delete(cell)
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    del delete
    del _list
    del configure
    del insert
    del remove


def ldap_tenant_group(parent):
    """Configures tenant CLI group"""
    formatter = cli.make_formatter(cli.TenantPrettyFormatter)

    @parent.group()
    def tenant():
        """Manage tenants"""
        pass

    @tenant.command()
    @click.option('-s', '--system', help='System eon id', type=int,
                  multiple=True, default=[])
    @click.argument('tenant')
    @cli.admin.ON_EXCEPTIONS
    def configure(system, tenant):
        """Create, get or modify tenant configuration"""
        admin_tnt = admin.Tenant(context.GLOBAL.ldap.conn)

        attrs = {}
        if system:
            attrs['systems'] = system

        if attrs:
            try:
                admin_tnt.create(tenant, attrs)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_tnt.update(tenant, attrs)

        try:
            tenant_obj = admin_tnt.get(tenant)
            tenant_obj['allocations'] = admin_tnt.allocations(tenant)
            cli.out(formatter(tenant_obj))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Tenant does not exist: %s' % tenant, err=True)

    @tenant.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured tenants"""
        admin_tnt = admin.Tenant(context.GLOBAL.ldap.conn)
        cli.out(formatter(admin_tnt.list({})))

    @tenant.command()
    @click.argument('tenant')
    @cli.admin.ON_EXCEPTIONS
    def delete(tenant):
        """Delete a tenant"""
        admin_tnt = admin.Tenant(context.GLOBAL.ldap.conn)
        try:
            admin_tnt.delete(tenant)
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Tenant does not exist: %s' % tenant, err=True)

    del delete
    del _list
    del configure


def ldap_allocations_group(parent):
    """Configures allocations CLI group"""
    # "too many branches" pylint warning.
    #
    # pylint: disable=R0912
    formatter = cli.make_formatter(cli.AllocationPrettyFormatter)

    @parent.group()
    def allocation():
        """Manage allocations"""
        pass

    @allocation.command()
    @click.option('-e', '--environment', help='Environment',
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']))
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def configure(environment, allocation):
        """Create, get or modify allocation configuration"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)

        attrs = {}
        if environment:
            attrs['environment'] = environment

        if attrs:
            try:
                admin_alloc.create(allocation, attrs)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_alloc.update(allocation, attrs)

        try:
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command()
    @click.option('-m', '--memory', help='Memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='CPU.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Disk.',
                  callback=cli.validate_disk)
    @click.option('-r', '--rank', help='Rank.', type=int, default=100)
    @click.option('-u', '--max-utilization',
                  help='Max utilization.', type=float)
    @click.option('-t', '--traits', help='Allocation traits', type=cli.LIST)
    @click.option('-l', '--label', help='Allocation label')
    @click.option('--cell', help='Cell.', required=True)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def reserve(allocation, cell, memory, cpu, disk, rank, max_utilization,
                traits, label):
        """Reserve capacity on a given cell"""
        admin_cell_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)
        data = {}
        if memory:
            data['memory'] = memory
        if cpu:
            data['cpu'] = cpu
        if disk:
            data['disk'] = disk
        if rank is not None:
            data['rank'] = rank
        if max_utilization is not None:
            data['max_utilization'] = max_utilization
        if traits:
            data['traits'] = cli.combine(traits)
        if label:
            if label == '-':
                label = None
            data['label'] = label

        try:
            admin_cell_alloc.create([cell, allocation], data)
        except ldap3.LDAPEntryAlreadyExistsResult:
            admin_cell_alloc.update([cell, allocation], data)

        try:
            admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command()
    @click.option('--pattern', help='Application name pattern.',
                  required=True)
    @click.option('--priority', help='Assigned priority.', type=int,
                  required=True)
    @click.option('--cell', help='Cell.', required=True)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def assign(allocation, cell, priority, pattern, delete):
        """Manage application assignments"""
        admin_cell_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)
        assignment = {'pattern': pattern, 'priority': priority}
        if delete:
            assignment['_delete'] = True

        data = {'assignments': [assignment]}
        if delete:
            admin_cell_alloc.update([cell, allocation], data)
        else:
            try:
                admin_cell_alloc.create([cell, allocation], data)
            except ldap3.LDAPEntryAlreadyExistsResult:
                admin_cell_alloc.update([cell, allocation], data)

        try:
            admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured allocations"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
        cli.out(formatter(admin_alloc.list({})))

    @allocation.command()
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def delete(allocation):
        """Delete an allocation"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
        try:
            admin_alloc.delete(allocation)
        except ldap3.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    del assign
    del reserve
    del delete
    del _list
    del configure


def init():
    """Return top level command handler"""

    @click.group()
    def ldap_group():
        """Manage Treadmill LDAP data"""
        pass

    cell_group(ldap_group)
    server_group(ldap_group)
    app_group(ldap_group)
    dns_group(ldap_group)
    app_groups_group(ldap_group)
    ldap_tenant_group(ldap_group)
    ldap_allocations_group(ldap_group)

    # Low level ldap access.
    direct_group(ldap_group)
    schema_group(ldap_group)
    init_group(ldap_group)

    return ldap_group
