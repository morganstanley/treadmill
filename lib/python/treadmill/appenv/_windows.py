"""Windows application environment.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from . import appenv

_LOGGER = logging.getLogger(__name__)


class WindowsAppEnvironment(appenv.AppEnvironment):
    """Windows Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    """

    def initialize(self, _params):
        """One time initialization of the Treadmill environment."""
        _LOGGER.info('Initializing once.')
