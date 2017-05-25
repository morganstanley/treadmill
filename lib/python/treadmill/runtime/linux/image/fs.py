"""The base implementation for fs plugins."""

import abc
import logging

import six

import stevedore
from stevedore import extension

from treadmill import appcfg
from treadmill import utils


_LOGGER = logging.getLogger(__name__)

_FS_PLUGIN_NAMESPACE = 'treadmill.image.{0}.fs'
_FS_PLUGIN_EXTENSION_MANAGER = None


@six.add_metaclass(abc.ABCMeta)
class FilesystemPluginBase(object):
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
    def configure(self, root_dir, app):
        """Configures the filesystem plugin."""
        pass


def _extension_manager(tm_env, name):
    """Gets the extension manager for image fs plugins."""
    # Disable W0603: Using the global statement
    global _FS_PLUGIN_EXTENSION_MANAGER  # pylint: disable=W0603

    if _FS_PLUGIN_EXTENSION_MANAGER is None:
        _FS_PLUGIN_EXTENSION_MANAGER = {}

    if name in _FS_PLUGIN_EXTENSION_MANAGER:
        return _FS_PLUGIN_EXTENSION_MANAGER[name]

    namespace = _FS_PLUGIN_NAMESPACE.format(name)
    _LOGGER.debug('Creating an extention manager for %r.', namespace)

    _FS_PLUGIN_EXTENSION_MANAGER[name] = extension.ExtensionManager(
        namespace=namespace,
        invoke_on_load=True,
        invoke_args=[tm_env],
        propagate_map_exceptions=True,
        on_load_failure_callback=utils.log_extension_failure
    )

    return _FS_PLUGIN_EXTENSION_MANAGER[name]


def _init(ext):
    _LOGGER.info('Initializing plugin %r.', ext.entry_point_target)
    ext.obj.init()


def init_plugins(tm_env):
    """Inits all plugins."""
    for app_type in appcfg.AppType:
        try:
            _extension_manager(tm_env, app_type.value).map(_init)
        except stevedore.exception.NoMatches:
            _LOGGER.info('There are no fs plugins for image %r.',
                         app_type.value)


def _configure(ext, root_dir, app):
    _LOGGER.info('Configuring plugin %r for root %r.', ext.entry_point_target,
                 root_dir)
    ext.obj.configure(root_dir, app)


def configure_plugins(tm_env, root_dir, app):
    """Configures all plugins."""
    try:
        _extension_manager(tm_env, app.type).map(_configure, root_dir, app)
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no fs plugins for image %r.', app.type)
