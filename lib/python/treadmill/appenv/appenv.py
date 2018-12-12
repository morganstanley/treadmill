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

from treadmill import watchdog


_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class AppEnvironment:
    """Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    """

    __slots__ = (
        'alerts_dir',
        'apps_dir',
        'app_events_dir',
        'app_types',
        'archives_dir',
        'bin_dir',
        'cache_dir',
        'cleaning_dir',
        'cleanup_apps_dir',
        'cleanup_dir',
        'cleanup_tombstone_dir',
        'configs_dir',
        'endpoints_dir',
        'images_dir',
        'init1_dir',
        'init_dir',
        'init_tombstone_dir',
        'root',
        'running_dir',
        'running_tombstone_dir',
        'tombstones_dir',
        'watchdogs',
        'watchdog_dir',
    )

    ALERTS_DIR = 'alerts'
    APPS_DIR = 'apps'
    BIN_DIR = 'bin'
    ARCHIVES_DIR = 'archives'
    CACHE_DIR = 'cache'
    CLEANING_DIR = 'cleaning'
    CLEANUP_DIR = 'cleanup'
    CLEANUP_APPS_DIR = 'cleanup_apps'
    CONFIG_DIR = 'configs'
    INIT_DIR = 'init'
    INIT1_DIR = 'init1'
    RUNNING_DIR = 'running'
    WATCHDOG_DIR = 'watchdogs'
    APP_EVENTS_DIR = 'appevents'
    IMAGES_DIR = 'images'
    TOMBSTONES_DIR = 'tombstones'
    ENDPOINTS_DIR = 'endpoints'

    def __init__(self, root):
        self.root = root

        self.alerts_dir = os.path.join(self.root, self.ALERTS_DIR)
        self.apps_dir = os.path.join(self.root, self.APPS_DIR)
        self.bin_dir = os.path.join(self.root, self.BIN_DIR)
        self.watchdog_dir = os.path.join(self.root, self.WATCHDOG_DIR)
        self.running_dir = os.path.join(self.root, self.RUNNING_DIR)
        self.cache_dir = os.path.join(self.root, self.CACHE_DIR)
        self.cleaning_dir = os.path.join(self.root, self.CLEANING_DIR)
        self.cleanup_dir = os.path.join(self.root, self.CLEANUP_DIR)
        self.cleanup_apps_dir = os.path.join(self.root, self.CLEANUP_APPS_DIR)
        self.configs_dir = os.path.join(self.root, self.CONFIG_DIR)
        self.app_events_dir = os.path.join(self.root, self.APP_EVENTS_DIR)
        self.archives_dir = os.path.join(self.root, self.ARCHIVES_DIR)
        self.images_dir = os.path.join(self.root, self.IMAGES_DIR)
        self.init_dir = os.path.join(self.root, self.INIT_DIR)
        self.init1_dir = os.path.join(self.root, self.INIT1_DIR)
        self.tombstones_dir = os.path.join(self.root, self.TOMBSTONES_DIR)
        self.cleanup_tombstone_dir = os.path.join(self.tombstones_dir,
                                                  self.CLEANUP_DIR)
        self.running_tombstone_dir = os.path.join(self.tombstones_dir,
                                                  self.RUNNING_DIR)
        self.init_tombstone_dir = os.path.join(self.tombstones_dir,
                                               self.INIT_DIR)
        self.endpoints_dir = os.path.join(self.root, self.ENDPOINTS_DIR)

        self.watchdogs = watchdog.Watchdog(self.watchdog_dir)

    @abc.abstractmethod
    def initialize(self, params):
        """One time initialization of the Treadmill environment.

        :params ``dict`` params:
            dictionary of parameters passed to the OS specific
            `meth:initialize` implementation.
        """
