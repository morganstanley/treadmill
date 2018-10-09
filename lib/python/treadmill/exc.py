"""Treadmill exceptions and utility functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import six

_LOGGER = logging.getLogger(__name__)


class TreadmillError(Exception):
    """Base class for all Treadmill errors.
    """

    __slots__ = (
    )

    @property
    def message(self):
        """The :class:`~TreadmillError`'s message.
        """
        # pylint: disable=unsubscriptable-object
        return self.args[0]

    def __init__(self, msg):
        super(TreadmillError, self).__init__(six.text_type(msg))

    def __str__(self):
        return self.message


class InvalidInputError(TreadmillError):
    """Non-fatal error, indicating incorrect input."""

    __slots__ = (
        'source',
    )

    def __init__(self, source, msg):
        super(InvalidInputError, self).__init__(msg=msg)
        self.source = source


class ContainerSetupError(TreadmillError):
    """Fatal error, indicating problem setting up container environment."""

    __slots__ = (
        'reason',
    )

    def __init__(self, msg, reason=None):
        super(ContainerSetupError, self).__init__(msg=msg)
        if reason is None:
            self.reason = 'unknown'
        else:
            self.reason = reason


class NodeSetupError(TreadmillError):
    """Fatal error, indicating problem initializing the node environment"""

    __slots__ = ()


class LocalFileNotFoundError(TreadmillError):
    """Thrown if the file cannot be found on the host."""

    __slots__ = ()


class NotFoundError(TreadmillError):
    """Thrown in REST API when a resource is not found"""

    __slots__ = ()


class FoundError(TreadmillError):
    """Thrown in REST API when a resource is found"""

    __slots__ = ()


class QuotaExceededError(TreadmillError):
    """Thrown if quota is exceeded."""

    __slots__ = ()
