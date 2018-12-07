"""LDAP based admin backend.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from . import _ldap
from . import base
from . import WrappedAdmin


class AdminLdapBackend(base.Backend):
    """Admin LDAP backend."""

    def __init__(self, uri, ldap_suffix,
                 user=None, password=None, connect_timeout=5, write_uri=None):
        self.conn = _ldap.Admin(
            uri, ldap_suffix,
            user=user, password=password,
            connect_timeout=connect_timeout, write_uri=write_uri
        )

    def init(self):
        """Initializes treadmill ldap namespace."""
        return self.conn.init()

    def schema(self):
        """Get schema."""
        return self.conn.schema()

    def update_schema(self, new_schema):
        """Safely update schema, preserving existing attribute types."""
        return self.conn.update_schema(new_schema)

    def connect(self):
        """Connect to backend server."""
        self.conn.connect()

    def partition(self):
        """Create Partition object."""
        return _ldap.Partition(WrappedAdmin(self.conn))

    def allocation(self):
        """Create Allocation object."""
        return _ldap.Allocation(WrappedAdmin(self.conn))

    def cell_allocation(self):
        """Create CellAllocation object."""
        return _ldap.CellAllocation(WrappedAdmin(self.conn))

    def tenant(self):
        """Create Tenant object."""
        return _ldap.Tenant(WrappedAdmin(self.conn))

    def cell(self):
        """Create Cell object."""
        return _ldap.Cell(WrappedAdmin(self.conn))

    def application(self):
        """Create Application object."""
        return _ldap.Application(WrappedAdmin(self.conn))

    def app_group(self):
        """Create AppGroup object."""
        return _ldap.AppGroup(WrappedAdmin(self.conn))

    def dns(self):
        """Create DNS object."""
        return _ldap.DNS(WrappedAdmin(self.conn))

    def server(self):
        """Create Server object."""
        return _ldap.Server(WrappedAdmin(self.conn))
