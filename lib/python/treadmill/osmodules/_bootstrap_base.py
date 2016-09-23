"""An interface for bootstrapping treadmill."""
from __future__ import absolute_import

import abc


class BootstrapBase(object):
    """Base interface for bootstrapping."""

    def __init__(self, src_dir, dst_dir, defaults):
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.defaults = defaults

    @abc.abstractmethod
    def install(self):
        """Installs the services."""

    @abc.abstractmethod
    def run(self):
        """Runs the services."""
