"""Implementation of treadmill admin ldap CLI server plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json

import click
from treadmill.admin import exc as admin_exceptions

from treadmill import cli
from treadmill import context


def init():

    """Configures server CLI group"""
    formatter = cli.make_formatter('server')

    @click.group()
    def server():
        """Manage server configuration.
        """

    @server.command()
    @click.option('-c', '--cell', help='Treadmll cell')
    @click.option('-t', '--traits', help='List of server traits',
                  multiple=True, default=[])
    @click.option('-p', '--partition', help='Server partition')
    @click.option('-d', '--data', help='Server specific data in JSON',
                  type=click.Path(exists=True, readable=True))
    @click.argument('server')
    @cli.admin.ON_EXCEPTIONS
    def configure(cell, traits, server, partition, data):
        """Create, get or modify server configuration"""
        admin_srv = context.GLOBAL.admin.server()

        attrs = {}
        if cell:
            attrs['cell'] = cell
        if traits:
            attrs['traits'] = cli.combine(traits)
        if partition:
            if partition == '-':
                partition = None
            attrs['partition'] = partition
        if data:
            with io.open(data, 'r') as fd:
                attrs['data'] = json.loads(fd.read())

        if attrs:
            try:
                admin_srv.create(server, attrs)
            except admin_exceptions.AlreadyExistsResult:
                admin_srv.update(server, attrs)

        try:
            cli.out(formatter(admin_srv.get(server, dirty=bool(attrs))))
        except admin_exceptions.NoSuchObjectResult:
            cli.bad_exit('Server does not exist: %s', server)

    @server.command(name='list')
    @click.option('-c', '--cell', help='Treadmll cell.')
    @click.option('-t', '--traits', help='List of server traits',
                  multiple=True, default=[])
    @click.option('-p', '--partition', help='Server partition')
    @cli.admin.ON_EXCEPTIONS
    def _list(cell, traits, partition):
        """List servers"""
        admin_srv = context.GLOBAL.admin.server()
        servers = admin_srv.list({'cell': cell,
                                  'traits': cli.combine(traits),
                                  'partition': partition})
        cli.out(formatter(servers))

    @server.command()
    @click.argument('servers', nargs=-1)
    @cli.admin.ON_EXCEPTIONS
    def delete(servers):
        """Delete server(s)"""
        admin_srv = context.GLOBAL.admin.server()
        for server in servers:
            admin_srv.delete(server)

    del delete
    del _list
    del configure

    return server
