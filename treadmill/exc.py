"""Treadmill exceptions and utility functions."""

import functools
import logging

from . import utils


_LOGGER = logging.getLogger(__name__)


class TreadmillError(Exception):
    """Base class for all Treadmill errors"""

    pass


class InvalidInputError(TreadmillError):
    """Non-fatal error, indicating incorrect input."""

    def __init__(self, source, msg):
        self.source = source
        self.message = msg
        super(InvalidInputError, self).__init__()


class ContainerSetupError(TreadmillError):
    """Fatal error, indicating problem setting up container environment."""
    pass


class NodeSetupError(TreadmillError):
    """Fatal error, indicating problem initializing the node environment"""
    pass


def exit_on_unhandled(func):
    """Decorator to exit thread on unhandled exception."""
    @functools.wraps(func)
    def _wrap(*args, **kwargs):
        """Wraps function to exit on unhandled exception."""
        try:
            return func(*args, **kwargs)
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Unhandled exception - exiting.')
            utils.sys_exit(-1)

    return _wrap
