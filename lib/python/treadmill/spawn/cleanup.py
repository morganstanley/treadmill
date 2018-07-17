"""Watches a directory for cleanup changes and deletes spawn instances.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import shutil

from treadmill import dirwatch
from treadmill import fs
from treadmill import spawn
from treadmill import subproc
from treadmill import supervisor
from treadmill.spawn import utils as spawn_utils

_LOGGER = logging.getLogger(__name__)


class Cleanup:
    """Treadmill spawn cleanup."""

    __slots__ = (
        'paths',
    )

    def __init__(self, root, buckets=spawn.BUCKETS):
        self.paths = spawn.SpawnPaths(root, buckets)
        fs.mkdir_safe(self.paths.cleanup_dir)

    def _nuke(self, scan_dir):
        """Tells the svscan instance to nuke the given scan dir."""
        _LOGGER.debug('Nuking directory %r', scan_dir)
        try:
            supervisor.control_svscan(scan_dir, (
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ))
        except subproc.CalledProcessError as ex:
            _LOGGER.warning(ex)

    def _on_created(self, path):
        """This is the handler function when files are created."""
        if os.path.basename(path).startswith('.'):
            return

        job, bucket, running = spawn_utils.get_instance_path(path, self.paths)

        _LOGGER.debug('Deleting - (%r, %r)', job, running)

        if not os.path.exists(running):
            _LOGGER.debug('Delete %r failed - does not exist', running)
            return

        fs.rm_safe(running)
        self._nuke(bucket)
        shutil.rmtree(job, ignore_errors=True)
        fs.rm_safe(path)

    def sync(self):
        """Sync cleanup dir to running folder."""
        for name in os.listdir(self.paths.cleanup_dir):
            self._on_created(os.path.join(self.paths.cleanup_dir, name))

    def get_dir_watch(self):
        """Construct a watcher for the cleanup directory."""
        watch = dirwatch.DirWatcher(self.paths.cleanup_dir)
        watch.on_created = self._on_created
        return watch
