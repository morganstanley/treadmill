"""Checkout LDAP infrastructure."""
from __future__ import absolute_import

import click

from treadmill import cli
from treadmill import context
from treadmill.checkout import ldap as ldap_test


def init():
    """Top level command handler."""

    @click.command('ldap')
    @click.option('--ldap-list', required=True, envvar='TREADMILL_LDAP_LIST',
                  type=cli.LIST)
    def check_ldap(ldap_list):
        """Checkout LDAP infra."""
        search_base = context.GLOBAL.ldap.search_base
        return lambda: ldap_test.test(ldap_list, search_base)

    return check_ldap
