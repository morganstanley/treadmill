"""Admin (LDAP) context."""


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

import logging

from treadmill.admin import exc as admin_exceptions

from treadmill.admin import ldapbackend
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def connect(uri, write_uri, ldap_suffix, user, password):
    """Connect to from parent context parameters."""
    _LOGGER.debug('Connecting to LDAP %s, %s', uri, ldap_suffix)
    conn = ldapbackend.AdminLdapBackend(uri, ldap_suffix, write_uri=write_uri,
                                        user=user, password=password)
    conn.connect()
    return conn


def resolve(ctx, attr):
    """Resolve context attribute."""

    if attr != 'zk_url':
        raise KeyError(attr)

    # TODO: in case of invalid cell it will throw ldap exception.
    #                need to standardize on ContextError raised lazily
    #                on first connection attempt, and keep resolve
    #                exception free.
    try:
        admin_cell = ctx.ldap.cell()
        cell = admin_cell.get(ctx.cell)
        scheme = cell.get('zk-auth-scheme')
        if not scheme:
            scheme = 'zookeeper'

        zk_hostports = [
            '{hostname}:{port}'.format(
                hostname=master['hostname'],
                port=master['zk-client-port']
            )
            for master in cell['masters']
        ]
        return '{scheme}://{username}@{hostports}/treadmill/{cell}'.format(
            scheme=scheme,
            username=cell['username'],
            hostports=','.join(zk_hostports),
            cell=ctx.cell
        )
    except admin_exceptions.NoSuchObjectResult:
        exception = context.ContextError(
            'Cell {} not defined in LDAP'.format(ctx.cell)
        )
        _LOGGER.debug(str(exception))
        raise exception


def init(_ctx):
    """Init context.
    """
