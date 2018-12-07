"""Admin module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
from ldap3.core import exceptions as ldap_exceptions

from . import _ldap
from . import exc

_LOGGER = logging.getLogger(__name__)


# Note: All the following code is for backward compatibility only.
# Once all usage is updated to the new API, _wrap_excs should be moved
# to _ldap and everything else should be removed.

# Disable warning about fake constructors
# pylint: disable=invalid-name

def Partition(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Partition(backend.conn)


def Allocation(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Allocation(backend.conn)


def CellAllocation(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.CellAllocation(backend.conn)


def Tenant(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Tenant(backend.conn)


def Cell(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Cell(backend.conn)


def Server(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Server(backend.conn)


def Application(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.Application(backend.conn)


def AppGroup(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.AppGroup(backend.conn)


def DNS(backend):
    """Fake constructor for backward compatiblity.
    """
    _LOGGER.debug('Using deprecated admin interface.')
    return _ldap.DNS(backend.conn)


def _wrap_excs(func):
    """Decorator to transform LDAP exceptions to Admin exceptions."""

    def wrapper(*args, **kwargs):
        """Wrapper that does the exception translation."""
        try:
            return func(*args, **kwargs)
        except ldap_exceptions.LDAPNoSuchObjectResult as e:
            raise exc.NoSuchObjectResult(e)
        except ldap_exceptions.LDAPEntryAlreadyExistsResult as e:
            raise exc.AlreadyExistsResult(e)
        except ldap_exceptions.LDAPBindError as e:
            raise exc.AdminConnectionError(e)
        except ldap_exceptions.LDAPInsufficientAccessRightsResult as e:
            raise exc.AdminAuthorizationError(e)
        except ldap_exceptions.LDAPOperationResult as e:
            raise exc.AdminBackendError(e)

    return wrapper


class WrappedAdmin():
    """Wrap the interface methods of _ldap.Admin to raise backend
    exceptions.
    """

    def __init__(self, conn):
        self._conn = conn

    def dn(self, ident):
        """Constructs dn."""
        return self._conn.dn(ident)

    @_wrap_excs
    def get(self, dn, query, attrs, **kwargs):
        """Gets LDAP object given dn."""
        return self._conn.get(dn, query, attrs, **kwargs)

    @_wrap_excs
    def paged_search(self, search_base, search_filter, **kwargs):
        """Call ldap paged search and return a generator of dn, entry tuples.
        """
        return self._conn.paged_search(search_base, search_filter, **kwargs)

    @_wrap_excs
    def create(self, dn, entry):
        """Creates LDAP record."""
        return self._conn.create(dn, entry)

    @_wrap_excs
    def update(self, dn, entry):
        """Updates LDAP record."""
        return self._conn.update(dn, entry)

    @_wrap_excs
    def remove(self, dn, entry):
        """Removes attributes from the record."""
        return self._conn.remove(dn, entry)

    @_wrap_excs
    def delete(self, dn):
        """Call ldap delete and raise exception on non-success."""
        return self._conn.delete(dn)
