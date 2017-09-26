"""Application environment.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging
import os

import six

from treadmill import fs
from treadmill import watchdog


_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class AppEnvironment(object):
    """Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    """

    __slots__ = (
        'apps_dir',
        'app_events_dir',
        'app_types',
        'archives_dir',
        'cache_dir',
        'cleanup_dir',
        'configs_dir',
        'images_dir',
        'init_dir',
        'metrics_dir',
        'root',
        'running_dir',
        'watchdogs',
        'watchdog_dir',
    )

    APPS_DIR = 'apps'
    ARCHIVES_DIR = 'archives'
    CACHE_DIR = 'cache'
    CLEANUP_DIR = 'cleanup'
    CONFIG_DIR = 'configs'
    INIT_DIR = 'init'
    RUNNING_DIR = 'running'
    METRICS_DIR = 'metrics'
    WATCHDOG_DIR = 'watchdogs'
    APP_EVENTS_DIR = 'appevents'
    IMAGES_DIR = 'images'

    def __init__(self, root):
        self.root = root

        self.apps_dir = os.path.join(self.root, self.APPS_DIR)
        self.watchdog_dir = os.path.join(self.root, self.WATCHDOG_DIR)
        self.running_dir = os.path.join(self.root, self.RUNNING_DIR)
        self.cache_dir = os.path.join(self.root, self.CACHE_DIR)
        self.cleanup_dir = os.path.join(self.root, self.CLEANUP_DIR)
        self.configs_dir = os.path.join(self.root, self.CONFIG_DIR)
        self.app_events_dir = os.path.join(self.root, self.APP_EVENTS_DIR)
        self.metrics_dir = os.path.join(self.root, self.METRICS_DIR)
        self.archives_dir = os.path.join(self.root, self.ARCHIVES_DIR)
        self.images_dir = os.path.join(self.root, self.IMAGES_DIR)
        self.init_dir = os.path.join(self.root, self.INIT_DIR)

        self.watchdogs = watchdog.Watchdog(self.watchdog_dir)

        fs.mkdir_safe(self.apps_dir)
        fs.mkdir_safe(self.watchdog_dir)
        fs.mkdir_safe(self.running_dir)
        fs.mkdir_safe(self.cache_dir)
        fs.mkdir_safe(self.cleanup_dir)
        fs.mkdir_safe(self.configs_dir)
        fs.mkdir_safe(self.app_events_dir)
        fs.mkdir_safe(self.metrics_dir)
        fs.mkdir_safe(self.archives_dir)
        fs.mkdir_safe(self.init_dir)

    @abc.abstractmethod
    def initialize(self, params):
        """One time initialization of the Treadmill environment.

        :params ``dict`` params:
            dictionary of parameters passed to the OS specific
            `meth:initialize` implementation.
        """
        pass
