"""Admin module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc

from . import admin


class Backend(metaclass=abc.ABCMeta):
    """Admin plugin interface."""
    pass


class AdminLdapBackend(Backend):
    """Admin LDAP backend."""

    def __init__(self, uri, ldap_suffix,
                 user=None, password=None, connect_timeout=5, write_uri=None):
        self.conn = admin.Admin(
            uri, ldap_suffix,
            user=user, password=password,
            connect_timeout=connect_timeout, write_uri=write_uri
        )

    def connect(self):
        """Connect to backend server."""
        self.conn.connect()

    def partition(self):
        """Create Partition object."""
        return admin.Partition(self.conn)

    def allocation(self):
        """Create Allocation object."""
        return admin.Allocation(self.conn)

    def cellAllocation(self):
        """Create CellAllocation object."""
        return admin.CellAllocation(self.conn)

    def tenant(self):
        """Create Tenant object."""
        return admin.Tenant(self.conn)

    def cell(self):
        """Create Cell object."""
        return admin.Cell(self.conn)

    def application(self):
        """Create Application object."""
        return admin.Application(self.conn)

    def appGroup(self):
        """Create AppGroup object."""
        return admin.AppGroup(self.conn)

    def dns(self):
        """Create DNS object."""
        return admin.DNS(self.conn)

    def server(self):
        """Create Server object."""
        return admin.Server(self.conn)
