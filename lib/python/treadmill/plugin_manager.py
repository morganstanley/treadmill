"""Plugin manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging
import os
import fnmatch

import pkg_resources

_LOGGER = logging.getLogger(__name__)

_FILTER = None


def _init_filter():
    """Init plugin filter from environment."""
    global _FILTER  # pylint: disable=global-statement
    if _FILTER is not None:
        return

    _FILTER = collections.defaultdict(list)
    _FILTER = _load_filter(os.environ.get('TREADMILL_PLUGIN_FILTER'))


def _load_filter(filter_str):
    """Load plugin filter from environment string."""

    if not filter_str:
        return {}

    filt = collections.defaultdict(list)
    for entry in filter_str.split(':'):
        section, pattern = entry.split('=')
        filt[section].extend(pattern.split(','))

    return filt


def _match(namespace, name):
    """Check if plugin is in the filter."""
    _init_filter()

    if namespace not in _FILTER:
        return True

    for pattern in _FILTER[namespace]:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def names(namespace):
    """Return extension names without loading the extensions."""
    return [
        entry.name for entry in pkg_resources.iter_entry_points(namespace)
        if _match(namespace, entry.name)
    ]


def load(namespace, name):
    """Return loaded module."""
    if not _match(namespace, name):
        # FIXME: Do not overload KeyError
        raise KeyError('Entry point not found: %r:%r' % (namespace, name))

    plugin = next(pkg_resources.iter_entry_points(namespace, name), None)
    if plugin is None:
        # FIXME: Do not overload KeyError
        raise KeyError('Entry point not found: %r:%r' % (namespace, name))

    instance = plugin.load()
    return instance


def load_all(namespace):
    """Load all plugins in the namespace."""
    return [
        entry.load() for entry in pkg_resources.iter_entry_points(namespace)
        if _match(namespace, entry.name)
    ]
