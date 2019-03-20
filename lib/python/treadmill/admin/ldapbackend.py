"""LDAP based admin backend.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from . import _ldap
from . import base
from . import WrappedAdmin

_LOGGER = logging.getLogger(__name__)


class AdminLdapBackend(base.Backend):
    """Admin LDAP backend.
    """
    __slots__ = (
        '_ldap_conn',
    )

    def __init__(self, uri, ldap_suffix,
                 user=None, password=None, connect_timeout=5, write_uri=None):
        self._ldap_conn = _ldap.Admin(
            uri, ldap_suffix,
            user=user, password=password,
            connect_timeout=connect_timeout, write_uri=write_uri
        )

    def init(self):
        """Initializes treadmill ldap namespace."""
        return self._ldap_conn.init()

    def schema(self):
        """Get schema."""
        return self._ldap_conn.schema()

    def update_schema(self, new_schema):
        """Safely update schema, preserving existing attribute types."""
        return self._ldap_conn.update_schema(new_schema)

    def list(self, search_base=None, search_filter=None, dirty=False):
        """List all objects DN in the admin backend.
        """
        search_res = self._ldap_conn.paged_search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope='SUBTREE',
            attributes=[],
            dirty=dirty
        )
        return [entry['dn'] for entry in search_res]

    def get(self, entry_dn, search_filter=None, attributes=None, dirty=False):
        """Return the raw data of a given ldap backend entry.

        :returns:
            ``tuple(str, dict)`` - (DN, Dict) of the request entry or None.
        """
        search_res = self._ldap_conn.paged_search(
            search_base=entry_dn,
            search_filter=search_filter,
            search_scope='BASE',
            attributes=attributes,
            dirty=dirty
        )
        entry = next(search_res, None)
        if entry:
            return entry['raw_attributes']
        else:
            return None

    def set(self, entry_dn, entry_data):
        """Set a DN to the given entry_data
        """
        self._ldap_conn.set(entry_dn, entry_data)

    def delete(self, entry_dn):
        """Delete a given entry.
        """
        self._ldap_conn.delete(entry_dn)

    def search(self, search_base=None, search_filter=None,
               search_scope='SUBTREE', attributes=None, dirty=False):
        """Raw search operation.

        :returns:
            ``[(dn, dict)]`` - Generator of dn and their data.
        """
        search_res = self._ldap_conn.paged_search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=attributes,
            dirty=dirty
        )
        return [
            (entry['dn'], entry['raw_attributes'])
            for entry in search_res
        ]

    # Base abstract method implementations below
    def connect(self):
        """Connect to backend server."""
        self._ldap_conn.connect()

    def partition(self):
        """Create Partition object."""
        return _ldap.Partition(WrappedAdmin(self._ldap_conn))

    def allocation(self):
        """Create Allocation object."""
        return _ldap.Allocation(WrappedAdmin(self._ldap_conn))

    def cell_allocation(self):
        """Create CellAllocation object."""
        return _ldap.CellAllocation(WrappedAdmin(self._ldap_conn))

    def tenant(self):
        """Create Tenant object."""
        return _ldap.Tenant(WrappedAdmin(self._ldap_conn))

    def cell(self):
        """Create Cell object."""
        return _ldap.Cell(WrappedAdmin(self._ldap_conn))

    def application(self):
        """Create Application object."""
        return _ldap.Application(WrappedAdmin(self._ldap_conn))

    def app_group(self):
        """Create AppGroup object."""
        return _ldap.AppGroup(WrappedAdmin(self._ldap_conn))

    def dns(self):
        """Create DNS object."""
        return _ldap.DNS(WrappedAdmin(self._ldap_conn))

    def server(self):
        """Create Server object."""
        return _ldap.Server(WrappedAdmin(self._ldap_conn))
