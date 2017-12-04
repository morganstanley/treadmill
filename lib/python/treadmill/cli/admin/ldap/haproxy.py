"""Implementation of treadmill admin ldap CLI haproxy plugin.
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
    """Configures HAProxy servers"""
    formatter = cli.make_formatter('haproxy')

    @click.group()
    def haproxy():
        """Manage HAProxies"""
        pass

    @haproxy.command()
    @click.option('-c', '--cell', help='Treadmll cell')
    @click.argument('haproxy')
    @cli.admin.ON_EXCEPTIONS
    def configure(cell, haproxy):
        """Create, get or modify HAProxy servers"""
        admin_haproxy = admin.HAProxy(context.GLOBAL.ldap.conn)

        attrs = {}
        if cell:
            attrs['cell'] = cell

        if attrs:
            try:
                admin_haproxy.create(haproxy, attrs)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_haproxy.update(haproxy, attrs)

        try:
            cli.out(formatter(admin_haproxy.get(haproxy)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('HAProxy does not exist: {}'.format(haproxy), err=True)

    @haproxy.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List partitions"""
        admin_haproxy = admin.HAProxy(context.GLOBAL.ldap.conn)
        haproxies = admin_haproxy.list({})

        cli.out(formatter(haproxies))

    @haproxy.command()
    @click.argument('haproxy')
    @cli.admin.ON_EXCEPTIONS
    def delete(haproxy):
        """Delete a partition"""
        admin_haproxy = admin.HAProxy(context.GLOBAL.ldap.conn)

        try:
            admin_haproxy.delete(haproxy)
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('HAProxy does not exist: {}'.format(haproxy), err=True)

    del configure
    del _list
    del delete

    return haproxy
