"""Treadmill Websocket APIs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)


def init(apis):
    """Module initialization."""
    handlers = []
    for apiname in apis:
        try:
            _LOGGER.info('Loading api: %s', apiname)
            wsapi_mod = plugin_manager.load('treadmill.websocket.api', apiname)
            handlers.extend(wsapi_mod.init())

        except ImportError as err:
            _LOGGER.warning('Unable to load %s api: %s', apiname, err)

    return handlers
