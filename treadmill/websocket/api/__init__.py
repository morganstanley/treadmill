"""Treadmill Websocket APIs"""


import logging
import importlib
import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)

_LOGGER = logging.getLogger(__name__)


def init(apis):
    """Module initialization."""
    handlers = []
    for apiname in apis:
        try:
            apimod = apiname.replace('-', '_')
            _LOGGER.info('Loading api: %s', apimod)

            wsapi_mod = importlib.import_module(
                'treadmill.websocket.api.' + apimod)
            # handlers.append(('/' + apimod, wsapi_mod.API))
            handlers.extend(wsapi_mod.init())

        except ImportError as err:
            _LOGGER.warn('Unable to load %s api: %s', apimod, err)

    return handlers
