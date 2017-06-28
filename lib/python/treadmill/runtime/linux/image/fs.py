"""The base implementation for fs plugins."""

import abc
import logging

import six

import stevedore

from treadmill import appcfg
from treadmill import plugin_manager


_LOGGER = logging.getLogger(__name__)

_FS_PLUGIN_NAMESPACE = 'treadmill.image.{0}.fs'


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
    def configure(self, container_dir, app):
        """Configures the filesystem plugin.

        :param ``str`` container_dir:
            Container base directtory.
        :param ``object`` app:
            Container manifest object.
        """
        pass


def _extension_manager(tm_env, name):
    """Gets the extension manager for image fs plugins."""
    _LOGGER.debug('Creating an extention manager for %r.', name)
    return plugin_manager.extensions(
        _FS_PLUGIN_NAMESPACE.format(name),
        invoke_on_load=True,
        invoke_args=[tm_env]
    )()


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


def _configure(ext, container_dir, app):
    _LOGGER.info('Configuring plugin %r for container_dir %r.',
                 ext.entry_point_target, container_dir)
    ext.obj.configure(container_dir, app)


def configure_plugins(tm_env, container_dir, app):
    """Configures all plugins."""
    try:
        _extension_manager(tm_env, app.type).map(
            _configure, container_dir, app
        )
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no fs plugins for image %r.', app.type)
