"""Implementation of treadmill admin ldap CLI direct plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import admin
from treadmill import cli
from treadmill import context


def init():
    """Direct ldap access CLI group"""

    @click.group()
    def direct():
        """Direct access to LDAP data.
        """

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
