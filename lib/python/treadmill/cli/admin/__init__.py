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

import kazoo
import kazoo.exceptions
import click
import dns.exception
import dns.resolver
import ldap3
from ldap3.core import exceptions as ldap_exceptions

import treadmill
from treadmill import restclient
from treadmill import cli
from treadmill import context
from treadmill import logging as tl
from treadmill import yamlwrapper as yaml
from treadmill import kerberoswrapper as kerberos
from treadmill.admin import exc as admin_exceptions


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


def _handle_krb_error(err):
    """Handle GSSAPI error."""
    msg = err.args[1][0]
    click.echo(msg, err=True)


ON_EXCEPTIONS = cli.handle_exceptions([
    (ldap_exceptions.LDAPInsufficientAccessRightsResult,
     'Error: access denied.'),
    (ldap_exceptions.LDAPBindError, None),
    (ldap_exceptions.LDAPNoSuchObjectResult, _handle_no_such_ldap_obj),
    (admin_exceptions.AdminAuthorizationError, 'Error: access denied.'),
    (admin_exceptions.AdminConnectionError, None),
    (admin_exceptions.NoSuchObjectResult, 'Error: resource does not exist.'),
    (kazoo.exceptions.NoAuthError, 'Error: not authorized.'),
    (kazoo.exceptions.NoNodeError, 'Error: resource does not exist.'),
    (kerberos.GSSError, _handle_krb_error),
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
    @click.option('--ldap', required=False,
                  envvar='TREADMILL_LDAP',
                  type=cli.LIST,
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.option('--ldap-master', required=False,
                  envvar='TREADMILL_LDAP_MASTER',
                  type=cli.LIST,
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.option('--ldap-user', required=False,
                  envvar='TREADMILL_LDAP_USER',
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.option('--ldap-pwd', required=False,
                  envvar='TREADMILL_LDAP_PWD',
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.option('--ldap-suffix', required=False,
                  envvar='TREADMILL_LDAP_SUFFIX',
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.pass_context
    def run(ctx):
        """Admin commands."""
        cli.init_logger('admin.json')

        log_level = logging.WARN
        if ctx.obj.get('logging.debug'):
            log_level = logging.DEBUG

        tl.set_log_level(log_level)

    return run
