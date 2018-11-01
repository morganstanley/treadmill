"""Plugin manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# XXX: importlib not regarded as standard lib on windows
import collections
import fnmatch
import importlib  # pylint: disable=wrong-import-order
import io
import json
import logging
import os


_LOGGER = logging.getLogger(__name__)

_FILTER = None


def _load_plugins():
    """Load plugins."""
    if 'TREADMILL_APPROOT' not in os.environ:
        return None

    plugins_file = os.path.join(
        os.environ['TREADMILL_APPROOT'],
        'plugins.json'
    )
    try:
        with io.open(plugins_file) as f:
            plugins = json.loads(f.read())
        return plugins
    except OSError as err:
        return None


# Load plugins on module import.
_PLUGINS = _load_plugins()


def _load_entry(entry):
    """Load plugin entry."""
    plugin = importlib.import_module(entry['module'])
    for extra in entry['attrs']:
        plugin = getattr(plugin, extra)
    return plugin


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


def _pkg_resources_names(namespace):
    """Return extension names without loading the extensions."""
    import pkg_resources

    return [
        entry.name for entry in pkg_resources.iter_entry_points(namespace)
        if _match(namespace, entry.name)
    ]


def _pkg_resources_load(namespace, name):
    """Return loaded module."""
    import pkg_resources

    if not _match(namespace, name):
        # FIXME: Do not overload KeyError
        raise KeyError('Entry point not found: %r:%r' % (namespace, name))

    plugin = next(pkg_resources.iter_entry_points(namespace, name), None)
    if plugin is None:
        # FIXME: Do not overload KeyError
        raise KeyError('Entry point not found: %r:%r' % (namespace, name))

    instance = plugin.load()
    return instance


def _pkg_resources_load_all(namespace):
    """Load all plugins in the namespace."""
    import pkg_resources

    return [
        entry.load() for entry in pkg_resources.iter_entry_points(namespace)
        if _match(namespace, entry.name)
    ]


def names(namespace):
    """Return extension names without loading the extensions."""
    if _PLUGINS:
        return _PLUGINS[namespace].keys()
    else:
        return _pkg_resources_names(namespace)


def load(namespace, name):
    """Return loaded module."""
    if _PLUGINS:
        return _load_entry(_PLUGINS[namespace][name])
    else:
        return _pkg_resources_load(namespace, name)


def load_all(namespace):
    """Load all plugins in the namespace."""
    if _PLUGINS:
        plugins = []
        for spec in _PLUGINS.get(namespace, {}).values():
            plugins.append(_load_entry(spec))
        return plugins
    else:
        return _pkg_resources_load_all(namespace)


def dump_cache(cache_file, distributions):
    """Write entry points in the distributions to the cache."""
    import pkg_resources

    cache = {}
    for dist in distributions:
        for section, entries in pkg_resources.get_entry_map(dist).items():
            if section not in cache:
                cache[section] = {}

            for name, entry in entries.items():
                cache[section][name] = {
                    'module': entry.module_name,
                    'attrs': list(entry.attrs)
                }

    with io.open(cache_file, 'w') as f:
        f.write(json.dumps(cache))
