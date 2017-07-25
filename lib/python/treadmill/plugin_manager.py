"""Plugin manager."""

import logging
import pkg_resources


_LOGGER = logging.getLogger(__name__)


def names(namespace):
    """Return extension names without loading the extensions."""
    return [entry.name for entry in pkg_resources.iter_entry_points(namespace)]


def load(namespace, name):
    """Return loaded module."""
    try:
        return pkg_resources.iter_entry_points(namespace, name).next().load()
    except StopIteration:
        raise KeyError('Entry point not found: %s:%s' % (namespace, name))


def load_all(namespace):
    """Load all plugins in the namespace."""
    return [entry.load()
            for entry in pkg_resources.iter_entry_points(namespace)]
