"""Treadmill master process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging


_LOGGER = logging.getLogger(__name__)


class ObjectNotFoundError(Exception):
    """Storage exception raised if object is not found."""
    pass


class Backend(object):
    """Master storage interface."""

    def __init__(self):
        pass

    def list(self, _path):
        """Return path listing."""
        return []

    def get(self, _path):
        """Return stored object given path."""
        return None

    def get_default(self, path, default=None):
        """Return stored object given path, default if not found."""
        try:
            self.get(path)
        except ObjectNotFoundError:
            return default

    def put(self, _path, _value):
        """Store object at a given path."""
        pass

    def exists(self, _path):
        """Check if object exists."""
        pass

    def ensure_exists(self, _path):
        """Ensure storage path exists."""
        pass

    def delete(self, _path):
        """Delete object given the path."""
        pass

    def update(self, _path, _data, check_content=False):
        """Set data into ZK node."""
        pass
