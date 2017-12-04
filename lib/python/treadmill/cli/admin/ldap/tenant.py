"""Implementation of treadmill admin ldap CLI tenant plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context


def init():
    """Configures tenant CLI group"""
    formatter = cli.make_formatter('tenant')

    @click.group()
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
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_tnt.update(tenant, attrs)

        try:
            tenant_obj = admin_tnt.get(tenant)
            tenant_obj['allocations'] = admin_tnt.allocations(tenant)
            cli.out(formatter(tenant_obj))
        except ldap_exceptions.LDAPNoSuchObjectResult:
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
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Tenant does not exist: %s' % tenant, err=True)

    del delete
    del _list
    del configure

    return tenant
