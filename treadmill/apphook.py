"""The base implementation for apphook plugins."""

import abc
import logging

import six

import stevedore

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_PLUGINS = plugin_manager.extensions('treadmill.apphooks')


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


def init(tm_env):
    """Inits all plugins."""
    for hook_name in _PLUGINS().names():
        try:
            _LOGGER.info('Initializing plugin %r.', hook_name)
            _PLUGINS()[hook_name].plugin(tm_env).init()
        except stevedore.exception.NoMatches:
            _LOGGER.info('There are no app hook plugins for %r.', hook_name)


def _configure(ext, app):
    _LOGGER.info('Configuring plugin %r', ext.entry_point_target)
    ext.obj.configure(app)


def configure(tm_env, app):
    """Configures all plugins."""
    try:
        for hook_name in _PLUGINS().names():
            _LOGGER.info('Configuring plugin %r', hook_name)
            _PLUGINS()[hook_name].plugin(tm_env).configure(app)
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no app hook plugins for %r.', hook_name)


def cleanup(tm_env, app):
    """Configures all plugins."""
    try:
        for hook_name in _PLUGINS().names():
            _LOGGER.info('Cleanup plugin %r', hook_name)
            _PLUGINS()[hook_name].plugin(tm_env).cleanup(app)
    except stevedore.exception.NoMatches:
        _LOGGER.info('There are no app hook plugins for %r.', hook_name)
