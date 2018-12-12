"""Base admin backend.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc


class Backend(metaclass=abc.ABCMeta):
    """Admin plugin interface.
    """

    @abc.abstractmethod
    def connect(self):
        """Connect to backend server.
        """

    @abc.abstractmethod
    def partition(self):
        """Create Partition object.
        """

    @abc.abstractmethod
    def allocation(self):
        """Create Allocation object.
        """

    @abc.abstractmethod
    def cell_allocation(self):
        """Create CellAllocation object.
        """

    @abc.abstractmethod
    def tenant(self):
        """Create Tenant object.
        """

    @abc.abstractmethod
    def cell(self):
        """Create Cell object.
        """

    @abc.abstractmethod
    def application(self):
        """Create Application object.
        """

    @abc.abstractmethod
    def app_group(self):
        """Create AppGroup object.
        """

    @abc.abstractmethod
    def dns(self):
        """Create DNS object.
        """

    @abc.abstractmethod
    def server(self):
        """Create Server object.
        """
