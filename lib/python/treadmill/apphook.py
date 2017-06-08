"""The base implementation for apphook plugins."""

import abc
import logging

import six

import stevedore
from stevedore import extension

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


_HOOK_PLUGIN_NAMESPACE = 'treadmill.apphooks'
_HOOK_PLUGIN_EXTENSION_MANAGER = None


@six.add_metaclass(abc.ABCMeta)
class AppHookPluginBase(object):
    """The base class of filesystem plugins for the image.

    :param tm_env:
        The Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    """
    __slots__ = (
        'tm_env'
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    @abc.abstractmethod
    def init(self):
        """Initializes the plugin."""
        pass

    @abc.abstractmethod
    def configure(self, app):
        """Configures the hook in plugin."""
        pass

    @abc.abstractmethod
    def cleanup(self, app):
        """cleanup the hook in plugin."""
        pass


def _extension_manager():
    """Gets the extension manager for image fs plugins."""
    # Disable W0603: Using the global statement
    global _HOOK_PLUGIN_EXTENSION_MANAGER  # pylint: disable=W0603

    if _HOOK_PLUGIN_EXTENSION_MANAGER is not None:
        return _HOOK_PLUGIN_EXTENSION_MANAGER

    _HOOK_PLUGIN_EXTENSION_MANAGER = extension.ExtensionManager(
        namespace=_HOOK_PLUGIN_NAMESPACE,
        propagate_map_exceptions=True,
        on_load_failure_callback=utils.log_extension_failure
    )

    return _HOOK_PLUGIN_EXTENSION_MANAGER


def list_all_hooks():
    """Lists all hook names."""
    return _extension_manager().names()


def init(tm_env):
    """Inits all plugins."""
    for hook_name in list_all_hooks():
        try:
            _LOGGER.info('Initializing plugin %r.', hook_name)
            plugin = _extension_manager()[hook_name].plugin(tm_env)
            plugin.init()
        except stevedore.exception.NoMatches:
            _LOGGER.info('There are no hook plugins for %r.', hook_name)


def _configure(ext, app):
    _LOGGER.info('Configuring plugin %r', ext.entry_point_target)
    ext.obj.configure(app)


def configure(tm_env, app):
    """Configures all plugins."""
    try:
        for hook_name in list_all_hooks():
            _LOGGER.info('Configuring plugin %r', hook_name)
            plugin = _extension_manager()[hook_name].plugin(tm_env)
            plugin.configure(app)
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no fs plugins for image %r.', hook_name)


def cleanup(tm_env, app):
    """Configures all plugins."""
    try:
        for hook_name in list_all_hooks():
            plugin = _extension_manager()[hook_name].plugin(tm_env)
            plugin.cleanup(app)
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no fs plugins for image %r.', hook_name)
