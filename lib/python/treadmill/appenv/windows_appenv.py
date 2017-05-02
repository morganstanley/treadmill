"""Windows application environment."""

from __future__ import absolute_import

import logging

from . import appenv


_LOGGER = logging.getLogger(__name__)


class WindowsAppEnvironment(appenv.AppEnvironment):
    """Windows Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    :param host_ip:
        Optional ip address of the host
    :type host_ip:
        `str`
    """

    def __init__(self, root, host_ip=None):
        super(WindowsAppEnvironment, self).__init__(root, host_ip)

    def initialize(self):
        """One time initialization of the Treadmill environment."""
        _LOGGER.info('Initializing once.')
