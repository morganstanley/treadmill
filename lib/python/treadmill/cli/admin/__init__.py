"""Implementation of treadmill-admin CLI plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import tempfile
import traceback

import click
import dns.exception
import dns.resolver
import kazoo
import kazoo.exceptions
import ldap3
from ldap3.core import exceptions as ldap_exceptions

import treadmill
from treadmill import restclient
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


def _handle_no_such_ldap_obj(err):
    """Handle LDAPNoSuchObjectResult exception."""
    if err.dn.find('ou=cells') != -1:
        rsrc_type = 'cell'
    elif err.dn.find('ou=allocations') != -1:
        rsrc_type = 'allocation'
    elif err.dn.find('ou=apps') != -1:
        rsrc_type = 'app'
    elif err.dn.find('ou=dns-servers') != -1:
        rsrc_type = 'dns configuration'
    else:
        rsrc_type = None

    if rsrc_type is None:
        rsrc_type = 'resource [%s]' % err.dn
    click.echo('Error: %s does not exist.' % rsrc_type, err=True)


ON_EXCEPTIONS = cli.handle_exceptions([
    (ldap_exceptions.LDAPInsufficientAccessRightsResult,
     'Error: access denied.'),
    (ldap_exceptions.LDAPBindError, 'Error: invalid credentials.'),
    (ldap_exceptions.LDAPNoSuchObjectResult, _handle_no_such_ldap_obj),
    (kazoo.exceptions.NoAuthError, 'Error: not authorized.'),
    (kazoo.exceptions.NoNodeError, 'Error: resource does not exist.'),
    (restclient.NotAuthorizedError, restclient.handle_not_authorized),
    (restclient.MaxRequestRetriesError, None),
    (dns.exception.Timeout, 'Error: DNS server timeout.'),
    (dns.resolver.NXDOMAIN, 'Error: Could not resolve DNS record.'),
    (dns.resolver.YXDOMAIN, 'Error: DNS error.'),
    (context.ContextError, None),
])


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.option('--ldap', envvar='TREADMILL_LDAP')
    @click.pass_context
    def run(ctx, ldap):
        """Admin commands."""
        cli.init_logger('admin.conf')

        log_level = logging.WARN
        if ctx.obj.get('logging.debug'):
            log_level = logging.DEBUG

        logging.getLogger('treadmill').setLevel(log_level)
        logging.getLogger().setLevel(log_level)

        if ldap:
            context.GLOBAL.ldap.url = ldap

    return run
