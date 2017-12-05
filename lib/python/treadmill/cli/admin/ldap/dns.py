"""Implementation of treadmill admin ldap CLI dns plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging

import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)


def init():  # pylint: disable=R0912
    """Configures Critical DNS CLI group"""
    formatter = cli.make_formatter('dns')

    _default_nameservers = ['localhost']

    @click.group()
    def dns():
        """Manage Critical DNS server configuration"""
        pass

    @dns.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--server', help='Server name',
                  required=False, type=cli.LIST)
    @click.option('-m', '--manifest', help='Load DNS from manifest file',
                  type=click.Path(exists=True, readable=True))
    @cli.admin.ON_EXCEPTIONS
    def configure(name, server, manifest):
        """Create, get or modify Critical DNS quorum"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)

        data = {}
        if manifest:
            with io.open(manifest, 'rb') as fd:
                data = yaml.load(stream=fd)

        if server is not None:
            data['server'] = server
        if data and 'nameservers' not in data:
            data['nameservers'] = _default_nameservers

        if 'server' in data and not isinstance(data['server'], list):
            data['server'] = data['server'].split(',')
        if 'rest-server' in data and (
                not isinstance(data['rest-server'], list)):
            data['rest-server'] = data['rest-server'].split(',')

        if data:
            _LOGGER.debug('data: %r', data)
            try:
                admin_dns.create(name, data)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_dns.update(name, data)

        try:
            cli.out(formatter(admin_dns.get(name)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('DNS entry does not exist: %s' % name, err=True)

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

    return dns
