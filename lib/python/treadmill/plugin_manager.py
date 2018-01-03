"""Plugin manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import pkg_resources

_LOGGER = logging.getLogger(__name__)


def names(namespace):
    """Return extension names without loading the extensions."""
    return [entry.name for entry in pkg_resources.iter_entry_points(namespace)]


def load(namespace, name):
    """Return loaded module."""
    try:
        return next(pkg_resources.iter_entry_points(namespace, name)).load()
    except StopIteration:
        raise KeyError('Entry point not found: %r:%r' % (namespace, name))


def load_all(namespace):
    """Load all plugins in the namespace."""
    return [entry.load()
            for entry in pkg_resources.iter_entry_points(namespace)]
