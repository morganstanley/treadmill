"""Admin module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
from ldap3.core import exceptions as ldap_exceptions

from . import exc

_LOGGER = logging.getLogger(__name__)


# Note: All the following code is for backward compatibility only.
# Once all usage is updated to the new API, _wrap_excs should be moved
# to _ldap and everything else should be removed.

def Partition(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.partition()


def Allocation(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.allocation()


def CellAllocation(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.cell_allocation()


def Tenant(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.tenant()


def Cell(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.cell()


def Server(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.server()


def Application(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.application()


def AppGroup(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.app_group()


def DNS(backend):
    """Fake constructor for backward compatiblity.
    """
    # pylint: disable=invalid-name
    _LOGGER.debug('Using deprecated admin interface.')
    return backend.dns()


def _wrap_excs(func):
    """Decorator to transform LDAP exceptions to Admin exceptions."""

    def wrapper(*args, **kwargs):
        """Wrapper that does the exception translation."""
        try:
            return func(*args, **kwargs)
        except ldap_exceptions.LDAPNoSuchObjectResult as err:
            raise exc.NoSuchObjectResult(err)
        except ldap_exceptions.LDAPEntryAlreadyExistsResult as err:
            raise exc.AlreadyExistsResult(err)
        except ldap_exceptions.LDAPBindError as err:
            raise exc.AdminConnectionError(err)
        except ldap_exceptions.LDAPInsufficientAccessRightsResult as err:
            raise exc.AdminAuthorizationError(err)
        except ldap_exceptions.LDAPOperationResult as err:
            raise exc.AdminBackendError(err)

    return wrapper


class WrappedAdmin():
    """Wrap the interface methods of _ldap.Admin to raise backend
    exceptions.
    """

    def __init__(self, conn):
        self._conn = conn

    def dn(self, ident):
        """Constructs dn."""
        # pylint: disable=invalid-name
        return self._conn.dn(ident)

    @_wrap_excs
    def get(self, entry_dn, query, attrs, **kwargs):
        """Gets LDAP object given dn."""
        return self._conn.get(entry_dn, query, attrs, **kwargs)

    @_wrap_excs
    def paged_search(self, search_base, search_filter, **kwargs):
        """Call ldap paged search and return a generator of dn, entry tuples.
        """
        return self._conn.paged_search(search_base, search_filter, **kwargs)

    @_wrap_excs
    def create(self, entry_dn, entry):
        """Creates LDAP record."""
        return self._conn.create(entry_dn, entry)

    @_wrap_excs
    def update(self, entry_dn, entry):
        """Updates LDAP record."""
        return self._conn.update(entry_dn, entry)

    @_wrap_excs
    def remove(self, entry_dn, entry):
        """Removes attributes from the record."""
        return self._conn.remove(entry_dn, entry)

    @_wrap_excs
    def delete(self, entry_dn):
        """Call ldap delete and raise exception on non-success."""
        return self._conn.delete(entry_dn)
