"""Bootstrap implementation for windows."""
from __future__ import absolute_import

from .. import _bootstrap_base


_MASTER_NOT_SUPPORTED_MESSAGE = "Windows does not support master services."


def default_install_dir():
    """Gets the base install directory."""
    return "C:"


class NodeBootstrap(_bootstrap_base.BootstrapBase):
    """For bootstrapping the node on windows."""

    def install(self):
        pass

    def run(self):
        pass
