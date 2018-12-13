"""Treadmill master process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging

_LOGGER = logging.getLogger(__name__)


class ObjectNotFoundError(Exception):
    """Storage exception raised if object is not found.
    """


class Backend(metaclass=abc.ABCMeta):
    """Master storage interface."""

    def __init__(self):
        """Backend constructor.
        """

    def list(self, _path):
        """Return path listing."""
        return []

    @abc.abstractmethod
    def get(self, path):
        """Return stored object given path.

        returns:
            ``object`` -- Object at path
        """

    @abc.abstractmethod
    def get_with_metadata(self, path):
        """Return stored object with metadata.

        returns:
            (``object``, ``object``) -- Object at path and its metadata.
        """

    def get_default(self, path, default=None):
        """Return stored object given path, default if not found."""
        try:
            return self.get(path)
        except ObjectNotFoundError:
            return default

    @abc.abstractmethod
    def put(self, path, value):
        """Store object at a given path.
        """

    @abc.abstractmethod
    def exists(self, path):
        """Check if object exists.
        """

    @abc.abstractmethod
    def ensure_exists(self, path):
        """Ensure storage path exists.
        """

    @abc.abstractmethod
    def delete(self, path):
        """Delete object given the path.
        """

    @abc.abstractmethod
    def update(self, path, data, check_content=False):
        """Set data into ZK node.
        """

    @abc.abstractmethod
    def event_object(self):
        """Create a new event object.
        """
