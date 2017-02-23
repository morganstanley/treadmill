"""
Watches a directory for manifest changes and invokes/deletes treadmill spawn
instances.
"""
from __future__ import absolute_import

import logging
import os
import shutil
import subprocess
import time

from treadmill import spawn
from treadmill import fs
from treadmill import idirwatch
from treadmill import subproc
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


class ManifestWatch(object):
    """Treadmill spawn watch helper class."""

    __slots__ = (
        'root',
        'init_dir',
        'manifest_dir',
        'zk_mirror_dir'
    )

    def __init__(self, root):
        self.root = root

        self.init_dir = os.path.join(self.root, spawn.INIT_DIR)
        self.manifest_dir = os.path.join(self.root, spawn.MANIFEST_DIR)
        self.zk_mirror_dir = os.path.join(self.root, spawn.ZK_MIRROR_DIR)

        fs.mkdir_safe(self.manifest_dir)
        fs.mkdir_safe(self.zk_mirror_dir)

        os.chmod(self.manifest_dir, 0o1777)

    def _check_path(self, path):
        """Checks if the path is valid."""
        if not os.path.exists(path):
            return False

        localpath = os.path.basename(path)
        if localpath.startswith('.'):
            return False

        if not localpath.endswith('.yml'):
            return False

        return True

    def _get_instance_path(self, path):
        """Gets the instance path for the app."""
        name = os.path.splitext(os.path.basename(path))[0]
        instance_path = os.path.join(self.init_dir, spawn.BASE_APP_DIR + name)
        return instance_path

    def _scan(self):
        """Tells the svscan instance to rescan the directory."""
        _LOGGER.debug('Scanning directory %r', self.init_dir)
        try:
            subproc.check_call(['s6-svscanctl', '-an', self.init_dir])
        except subprocess.CalledProcessError as ex:
            _LOGGER.warning(ex)

    def _create_instance(self, path):
        """Create an spawn instance."""
        instance_path = self._get_instance_path(path)

        _LOGGER.debug('Creating - %r', instance_path)

        if os.path.exists(instance_path):
            return

        fs.mkdir_safe(instance_path)
        fs.mkdir_safe(os.path.join(instance_path, 'log'))

        utils.create_script(os.path.join(instance_path, 'run'),
                            'spawn.run', manifest_path=path)

        utils.create_script(os.path.join(instance_path, 'finish'),
                            'spawn.finish', manifest_path=path)

        utils.create_script(os.path.join(instance_path, 'log', 'run'),
                            'spawn.log.run')

        self._scan()

    def _delete_instance(self, path):
        """Delete an spawn instance."""
        instance_path = self._get_instance_path(path)

        _LOGGER.debug('Deleting - %r', instance_path)

        if not os.path.exists(instance_path):
            return

        try:
            subproc.check_call([
                's6-svc', '-wD', '-T', '2000', '-d', instance_path
            ])
        except subprocess.CalledProcessError as ex:
            _LOGGER.warning(ex)

        time.sleep(0.5)

        try:
            shutil.rmtree(instance_path)
        except OSError as ex:
            _LOGGER.warning(ex)

        self._scan()

    def _on_created(self, path):
        """This is the handler function when new files are seen."""
        if not self._check_path(path):
            return

        _LOGGER.info('New manifest file - %r', path)

        self._create_instance(path)

    def _on_deleted(self, path):
        """This is the handler function when files are deleted."""
        _LOGGER.info('Deleted manifest file - %r', path)

        self._delete_instance(path)

    def sync(self):
        """Sync manifest dir to init folder."""
        manifests = set()
        directories = set()

        for manifest in os.listdir(self.manifest_dir):
            if self._check_path(manifest):
                manifests.add(manifest)

        for dirname in os.listdir(self.init_dir):
            if dirname.startswith(spawn.BASE_APP_DIR):
                directories.add(dirname[len(spawn.BASE_APP_DIR):] + '.yml')

        diffs = manifests.symmetric_difference(directories)

        for diff in diffs:
            if diff in directories:
                self._delete_instance(diff)
            else:
                self._create_instance(diff)

    def get_dir_watch(self):
        """Construct a watcher for the manifest directory."""
        watch = idirwatch.DirWatcher(self.manifest_dir)
        watch.on_created = self._on_created
        watch.on_deleted = self._on_deleted
        return watch
