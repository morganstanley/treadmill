"""Checkout LDAP infrastructure.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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
        ldap_suffix = context.GLOBAL.ldap_suffix
        return lambda: ldap_test.test(ldap_list, ldap_suffix)

    return check_ldap
