"""Manages Treadmill node environment initialization."""
from __future__ import absolute_import

import logging
import os

if os.name == 'posix':
    from treadmill import fs
    from treadmill import iptables

_LOGGER = logging.getLogger(__name__)


def initialize(tm_env):
    """One time initialization of the Treadmill environment."""
    _LOGGER.info('Initializing once.')

    if os.name == 'posix':
        # Flush all rules in iptables nat and mangle tables (it is assumed that
        # none but Treadmill manages these tables) and bulk load all the
        # Treadmill static rules
        iptables.initialize(tm_env.host_ip)

        # Initialize network rules
        tm_env.rules.initialize()

        # Initialize FS plugins.
        fs.init_plugins(tm_env.root)
