"""
Watches a directory for manifest changes and creates treadmill spawn instances.
"""
from __future__ import absolute_import

import json
import logging
import os
import subprocess

from treadmill import spawn
from treadmill import fs
from treadmill import dirwatch
from treadmill import subproc
from treadmill import utils
from treadmill.spawn import utils as spawn_utils
from treadmill.spawn import instance

_LOGGER = logging.getLogger(__name__)


class ManifestWatch(object):
    """Treadmill spawn manifest watch."""

    __slots__ = (
        'paths'
    )

    def __init__(self, root, buckets=spawn.BUCKETS):
        self.paths = spawn.SpawnPaths(root, buckets)
        fs.mkdir_safe(self.paths.manifest_dir)
        os.chmod(self.paths.manifest_dir, 0o1777)

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

    def _scan(self, scan_dir):
        """Tells the svscan instance to rescan the given scan dir."""
        _LOGGER.debug('Scanning directory %r', scan_dir)
        try:
            subproc.check_call(['s6-svscanctl', '-a', scan_dir])
        except subprocess.CalledProcessError as ex:
            _LOGGER.warning(ex)

    def _create_instance(self, path):
        """Create an spawn instance."""
        job, bucket, running = spawn_utils.get_instance_path(path, self.paths)

        _LOGGER.debug('Creating - (%r, %r)', job, running)

        if os.path.exists(running):
            _LOGGER.debug('Create %r failed - already exists', running)
            return

        inst = instance.Instance(path)
        data_dir = os.path.join(job, spawn.JOB_DATA_DIR)

        fs.mkdir_safe(job)
        fs.mkdir_safe(data_dir)

        utils.create_script(
            os.path.join(job, 'run'),
            'spawn.run',
            id=inst.id,
            name=inst.name,
            cellapi=self.paths.cellapi_sock,
            zk2fs=self.paths.zk_mirror_dir)

        utils.create_script(
            os.path.join(job, 'finish'),
            'spawn.finish',
            id=inst.id,
            cellapi=self.paths.cellapi_sock,
            cleanup=self.paths.cleanup_dir,
            stop=inst.settings['stop'],
            reconnect=inst.settings['reconnect'],
            reconnect_timeout=inst.settings['reconnect_timeout'])

        with open(os.path.join(data_dir, 'manifest'), 'w') as f:
            json.dump(inst.manifest, f)

        with open(os.path.join(job, 'timeout-finish'), 'w') as f:
            f.write(str(spawn.JOB_FINISH_TIMEOUT))

        fs.symlink_safe(running, job)

        self._scan(bucket)

    def _on_created(self, path):
        """This is the handler function when new files are seen."""
        if not self._check_path(path):
            return

        _LOGGER.info('New manifest file - %r', path)
        self._create_instance(path)
        _LOGGER.info('Created, now removing - %r', path)
        fs.rm_safe(path)

    def sync(self):
        """Sync manifest dir to running folder."""
        for name in os.listdir(self.paths.manifest_dir):
            self._on_created(os.path.join(self.paths.manifest_dir, name))

    def get_dir_watch(self):
        """Construct a watcher for the manifest directory."""
        watch = dirwatch.DirWatcher(self.paths.manifest_dir)
        watch.on_created = self._on_created
        return watch
