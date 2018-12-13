"""The base implementation for fs plugins.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging

import six

from treadmill import appcfg
from treadmill import plugin_manager


_LOGGER = logging.getLogger(__name__)

_FS_PLUGIN_NAMESPACE = 'treadmill.image.{0}.fs'


@six.add_metaclass(abc.ABCMeta)
class FilesystemPluginBase:
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
    def configure(self, container_dir, app):
        """Configures the filesystem plugin.

        :param ``str`` container_dir:
            Container base directtory.
        :param ``object`` app:
            Container manifest object.
        """


def init_plugins(tm_env):
    """Inits all plugins.
    """
    for app_type in appcfg.AppType:
        namespace = _FS_PLUGIN_NAMESPACE.format(app_type.value)
        for plugin in plugin_manager.load_all(namespace):
            plugin(tm_env).init()


def configure_plugins(tm_env, container_dir, app):
    """Configures all plugins.
    """
    namespace = _FS_PLUGIN_NAMESPACE.format(app.type)
    for plugin in plugin_manager.load_all(namespace):
        plugin(tm_env).configure(container_dir, app)
