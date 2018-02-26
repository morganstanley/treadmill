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
        'bin_dir',
        'cache_dir',
        'cleaning_dir',
        'cleanup_apps_dir',
        'cleanup_dir',
        'cleanup_tombstone_dir',
        'configs_dir',
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

    def __init__(self, root):
        self.root = root

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

        self.watchdogs = watchdog.Watchdog(self.watchdog_dir)

        fs.mkdir_safe(self.apps_dir)
        fs.mkdir_safe(self.bin_dir)
        fs.mkdir_safe(self.watchdog_dir)
        fs.mkdir_safe(self.running_dir)
        fs.mkdir_safe(self.cache_dir)
        fs.mkdir_safe(self.cleaning_dir)
        fs.mkdir_safe(self.cleanup_dir)
        fs.mkdir_safe(self.cleanup_apps_dir)
        fs.mkdir_safe(self.configs_dir)
        fs.mkdir_safe(self.app_events_dir)
        fs.mkdir_safe(self.archives_dir)
        fs.mkdir_safe(self.init_dir)
        fs.mkdir_safe(self.init1_dir)
        fs.mkdir_safe(self.tombstones_dir)
        fs.mkdir_safe(self.cleanup_tombstone_dir)
        fs.mkdir_safe(self.running_tombstone_dir)
        fs.mkdir_safe(self.init_tombstone_dir)

    @abc.abstractmethod
    def initialize(self, params):
        """One time initialization of the Treadmill environment.

        :params ``dict`` params:
            dictionary of parameters passed to the OS specific
            `meth:initialize` implementation.
        """
        pass
