"""Implementation of treadmill admin ldap CLI cell plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io

import click
from treadmill.admin import exc as admin_exceptions

from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


def init():
    """Configures cell CLI group"""
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    formatter = cli.make_formatter('cell')

    @click.group()
    @cli.admin.ON_EXCEPTIONS
    def cell():
        """Manage cell configuration.
        """

    @cell.command()
    @click.option('-v', '--version', help='Version.')
    @click.option('-r', '--root', help='Distro root.')
    @click.option('-l', '--location', help='Cell location.')
    @click.option('-u', '--username', help='Cell proid account.')
    @click.option('-d', '--data', help='Cell specific data in YAML',
                  type=click.Path(exists=True, readable=True))
    @click.option('--status', help='Cell status')
    @click.option('--traits', help='Traits enabled for the cell.',
                  type=cli.LIST)
    @click.option('-a', '--zk-auth-scheme', help='Zookeeper auth scheme')
    @click.option('-m', '--manifest', help='Load cell from manifest file.',
                  type=click.Path(exists=True, readable=True))
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def configure(cell, version, root, location, username, data, status,
                  traits, zk_auth_scheme, manifest):
        """Create, get or modify cell configuration"""
        admin_cell = context.GLOBAL.admin.cell()
        attrs = {}
        if manifest:
            with io.open(manifest, 'rb') as fd:
                attrs = yaml.load(stream=fd)

        if version:
            attrs['version'] = version
        if root:
            if root == '-':
                root = None
            attrs['root'] = root
        if location:
            attrs['location'] = location
        if username:
            attrs['username'] = username
        if status:
            attrs['status'] = status
        if traits:
            attrs['traits'] = traits
        if zk_auth_scheme:
            if zk_auth_scheme == '-':
                zk_auth_scheme = None
            attrs['zk-auth-scheme'] = zk_auth_scheme
        if data:
            with io.open(data, 'rb') as fd:
                attrs['data'] = yaml.load(stream=fd)

        if attrs:
            try:
                admin_cell.create(cell, attrs)
            except admin_exceptions.AlreadyExistsResult:
                admin_cell.update(cell, attrs)

        try:
            cli.out(formatter(admin_cell.get(cell, dirty=bool(attrs))))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command()
    @click.option('--idx', help='Master index.',
                  type=click.Choice(['1', '2', '3', '4', '5']),
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
        admin_cell = context.GLOBAL.admin.cell()
        cell_attrs = admin_cell.get(cell)
        masters = cell_attrs.get('masters', [])
        # remove current idx from masters
        masters = [master for master in masters if master['idx'] != idx]

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
        masters.append(data)

        attrs = {
            'masters': masters
        }
        try:
            admin_cell.update(cell, attrs)
            cli.out(formatter(admin_cell.get(cell, dirty=True)))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command()
    @click.option('--idx', help='Master index.',
                  type=click.Choice(['1', '2', '3']),
                  required=True)
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def remove(cell, idx):
        """Remove master server from a cell"""
        admin_cell = context.GLOBAL.admin.cell()
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
            cli.out(formatter(admin_cell.get(cell, dirty=True)))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    @cell.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """Displays master servers"""
        admin_cell = context.GLOBAL.admin.cell()
        cells = admin_cell.list({})
        cli.out(formatter(cells))

    @cell.command()
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def delete(cell):
        """Delete a cell"""
        admin_cell = context.GLOBAL.admin.cell()

        try:
            admin_cell.delete(cell)
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Cell does not exist: %s' % cell, err=True)

    del delete
    del _list
    del configure
    del insert
    del remove

    return cell
