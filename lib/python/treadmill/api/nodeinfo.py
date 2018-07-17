"""Implementation of allocation API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import discovery
from treadmill import context


_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill Local REST api."""

    def __init__(self):

        def _get(hostname):
            """Get hostname nodeinfo endpoint info."""
            _LOGGER.info('Redirect: %s', hostname)
            discovery_iter = discovery.iterator(
                context.GLOBAL.zk.conn,
                'root.%s' % hostname, 'nodeinfo', False
            )

            for (_app, hostport) in discovery_iter:
                if not hostport:
                    continue

                _LOGGER.info('Found: %s - %s', hostname, hostport)
                return hostport

            _LOGGER.info('nodeinfo not found: %s', hostname)
            return None

        self.get = _get
