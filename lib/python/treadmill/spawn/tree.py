"""Creates a supervision tree which splits the jobs into buckets."""
from __future__ import absolute_import

import logging
import os
import shutil

from treadmill import fs
from treadmill import spawn
from treadmill import utils
from treadmill.spawn import utils as spawn_utils

_LOGGER = logging.getLogger(__name__)


class Tree(object):
    """Treadmill spawn tree."""

    __slots__ = (
        'root',
        'svscan_tree_dir',
        'running_dir',
        'buckets',
        'max_per_bucket'
    )

    def __init__(self, root, buckets=spawn.BUCKETS,
                 max_per_bucket=spawn.MAX_PER_BUCKET):
        self.root = root
        self.buckets = buckets
        self.max_per_bucket = max_per_bucket

        self.svscan_tree_dir = os.path.join(self.root, spawn.SVSCAN_TREE_DIR)
        self.running_dir = os.path.join(self.root, spawn.RUNNING_DIR)

    def create(self):
        """Create the directory structure for the tree."""
        dirs = set()

        for bucket in range(self.buckets):
            bucket_formatted = spawn_utils.format_bucket(bucket)
            dirs.add(bucket_formatted)

            _LOGGER.debug('Adding bucket %r.', bucket_formatted)

            app = os.path.join(self.svscan_tree_dir, bucket_formatted)
            log = os.path.join(app, 'log')

            running = os.path.join(self.running_dir, bucket_formatted)
            svscan = os.path.join(running, '.s6-svscan')

            fs.mkdir_safe(app)
            fs.mkdir_safe(log)
            fs.mkdir_safe(running)
            fs.mkdir_safe(svscan)

            utils.create_script(
                os.path.join(app, 'run'),
                'svscan.run',
                max=self.max_per_bucket,
                service_dir=running
            )

            utils.create_script(
                os.path.join(log, 'run'),
                'logger.run'
            )

            utils.create_script(
                os.path.join(svscan, 'finish'),
                'svscan.finish',
                timeout=4800
            )

        for app_dir in os.listdir(self.svscan_tree_dir):
            if not app_dir.startswith('.') and app_dir not in dirs:
                path = os.path.join(self.svscan_tree_dir, app_dir)
                _LOGGER.debug('Removing bucket (%r) %r.',
                              spawn.SVSCAN_TREE_DIR, path)
                shutil.rmtree(path, ignore_errors=True)

        for run_dir in os.listdir(self.running_dir):
            if not run_dir.startswith('.') and run_dir not in dirs:
                path = os.path.join(self.running_dir, run_dir)
                _LOGGER.debug('Removing bucket (%r))  %r.',
                              spawn.RUNNING_DIR, path)
                shutil.rmtree(path, ignore_errors=True)
