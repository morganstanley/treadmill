"""Admin (LDAP) context."""


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

import logging

from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def connect(url, ldap_suffix, user, password):
    """Connect to from parent context parameters."""
    _LOGGER.debug('Connecting to LDAP %s, %s', url, ldap_suffix)
    conn = admin.Admin(url, ldap_suffix,
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
        admin_cell = admin.Cell(ctx.ldap.conn)
        cell = admin_cell.get(ctx.cell)
        zk_hostports = [
            '%s:%s' % (master['hostname'], master['zk-client-port'])
            for master in cell['masters']
        ]
        return 'zookeeper://%s@%s/treadmill/%s' % (
            cell['username'],
            ','.join(zk_hostports),
            ctx.cell
        )
    except ldap_exceptions.LDAPNoSuchObjectResult:
        exception = context.ContextError(
            'Cell not defined in LDAP {}'.format(ctx.cell)
        )
        _LOGGER.debug(str(exception))
        raise exception


def init(_ctx):
    """Init context."""
    pass
