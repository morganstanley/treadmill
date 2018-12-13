"""The base implementation for apphook plugins.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging

import six

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_PLUGINS_NS = 'treadmill.apphooks'


@six.add_metaclass(abc.ABCMeta)
class AppHookPluginBase:
    """The base class of filesystem plugins for the image.

    :param tm_env:
        The Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    """

    __slots__ = (
        'tm_env',
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    @abc.abstractmethod
    def init(self):
        """Initializes the plugin.
        """

    @abc.abstractmethod
    def configure(self, app, container_dir):
        """Configures the hook in plugin.
        """

    @abc.abstractmethod
    def cleanup(self, app, container_dir):
        """cleanup the hook in plugin.
        """


def init(tm_env):
    """Inits all plugins.
    """
    for hook in plugin_manager.load_all(_PLUGINS_NS):
        _LOGGER.info('Initializing plugin %r.', hook)
        hook(tm_env).init()


def configure(tm_env, app, container_dir):
    """Configures all plugins.
    """
    for hook in plugin_manager.load_all(_PLUGINS_NS):
        _LOGGER.info('Configuring plugin %r.', hook)
        hook(tm_env).configure(app, container_dir)


def cleanup(tm_env, app, container_dir):
    """Cleanup all plugins.
    """
    for hook in plugin_manager.load_all(_PLUGINS_NS):
        _LOGGER.info('Initializing plugin %r.', hook)
        hook(tm_env).cleanup(app, container_dir)
