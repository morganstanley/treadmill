"""Watches a directory for manifest changes and creates spawn instances.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os

import six

from treadmill import spawn
from treadmill import fs
from treadmill import dirwatch
from treadmill import subproc
from treadmill import supervisor
from treadmill import templates
from treadmill import utils
from treadmill.spawn import utils as spawn_utils
from treadmill.spawn import instance

_LOGGER = logging.getLogger(__name__)


class ManifestWatch:
    """Treadmill spawn manifest watch."""

    __slots__ = (
        'paths',
    )

    def __init__(self, root, buckets=spawn.BUCKETS):
        self.paths = spawn.SpawnPaths(root, buckets)
        fs.mkdir_safe(self.paths.manifest_dir)
        os.chmod(self.paths.manifest_dir, 0o1777)

        tmp_path = os.path.join(self.paths.manifest_dir, '.tmp')
        fs.mkdir_safe(tmp_path)
        os.chmod(tmp_path, 0o1777)

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
            supervisor.control_svscan(scan_dir,
                                      supervisor.SvscanControlAction.alarm)
        except subproc.CalledProcessError as ex:
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

        templates.create_script(
            os.path.join(job, 'run'),
            'spawn.run',
            id=inst.id,
            name=inst.name,
            service_exit=inst.settings.get('service_exit', False),
            **subproc.get_aliases()
        )

        templates.create_script(
            os.path.join(job, 'finish'),
            'spawn.finish',
            id=inst.id,
            stop=inst.settings.get('stop', False),
            reconnect=inst.settings.get('reconnect', False),
            reconnect_timeout=inst.settings.get('reconnect_timeout', 0),
            **subproc.get_aliases()
        )

        with io.open(os.path.join(data_dir, 'manifest'), 'w') as f:
            f.writelines(
                utils.json_genencode(inst.manifest)
            )

        with io.open(os.path.join(job, 'timeout-finish'), 'w') as f:
            f.write(six.text_type(spawn.JOB_FINISH_TIMEOUT))

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
