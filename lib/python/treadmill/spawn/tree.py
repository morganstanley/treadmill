"""Creates a supervision tree which splits the jobs into buckets.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import shutil

from treadmill import fs
from treadmill import spawn
from treadmill import subproc
from treadmill import supervisor
from treadmill import templates
from treadmill import utils
from treadmill import zknamespace
from treadmill.spawn import utils as spawn_utils
from treadmill.trace.app import zk as app_zk

_LOGGER = logging.getLogger(__name__)


class Tree:
    """Treadmill spawn tree."""

    __slots__ = (
        'paths',
        'buckets',
        'max_per_bucket'
    )

    def __init__(self, root, buckets=spawn.BUCKETS,
                 max_per_bucket=spawn.MAX_PER_BUCKET):
        self.buckets = buckets
        self.paths = spawn.SpawnPaths(root, buckets)
        self.max_per_bucket = max_per_bucket

    def create(self):
        """Create the directory structure for the tree."""
        env = {
            'TREADMILL_SPAWN_ZK2FS': self.paths.zk_mirror_dir,
            'TREADMILL_SPAWN_ZK2FS_SHARDS':
                str(zknamespace.TRACE_SHARDS_COUNT),
            'TREADMILL_SPAWN_ZK2FS_SOW': app_zk.TRACE_SOW_DIR,
            'TREADMILL_SPAWN_CELLAPI_SOCK': self.paths.cellapi_sock,
            'TREADMILL_SPAWN_CLEANUP': self.paths.cleanup_dir,
        }
        supervisor.create_environ_dir(self.paths.env_dir, env)

        dirs = set()
        for bucket in range(self.buckets):
            bucket_formatted = spawn_utils.format_bucket(bucket)
            dirs.add(bucket_formatted)

            _LOGGER.debug('Adding bucket %r.', bucket_formatted)

            app = os.path.join(self.paths.svscan_tree_dir, bucket_formatted)
            log = os.path.join(app, 'log')

            running = os.path.join(self.paths.running_dir, bucket_formatted)
            svscan = os.path.join(running, '.s6-svscan')

            fs.mkdir_safe(app)
            fs.mkdir_safe(log)
            fs.mkdir_safe(running)
            fs.mkdir_safe(svscan)

            templates.create_script(
                os.path.join(app, 'run'),
                's6.svscan.run',
                max=self.max_per_bucket,
                service_dir=running,
                _alias=subproc.get_aliases()
            )

            templates.create_script(
                os.path.join(log, 'run'),
                's6.logger.run',
                logdir='.',
                _alias=subproc.get_aliases()
            )

            templates.create_script(
                os.path.join(svscan, 'finish'),
                's6.svscan.finish',
                timeout=4800,
                _alias=subproc.get_aliases()
            )

        for app_dir in os.listdir(self.paths.svscan_tree_dir):
            if not app_dir.startswith('.') and app_dir not in dirs:
                path = os.path.join(self.paths.svscan_tree_dir, app_dir)
                _LOGGER.debug('Removing bucket (%r) %r.',
                              spawn.SVSCAN_TREE_DIR, path)
                shutil.rmtree(path, ignore_errors=True)

        for run_dir in os.listdir(self.paths.running_dir):
            if not run_dir.startswith('.') and run_dir not in dirs:
                path = os.path.join(self.paths.running_dir, run_dir)
                _LOGGER.debug('Removing bucket (%r))  %r.',
                              spawn.RUNNING_DIR, path)
                shutil.rmtree(path, ignore_errors=True)

    def run(self):
        """Exec into the tree."""
        s6_envdir = subproc.resolve('s6_envdir')
        utils.sane_execvp(s6_envdir, [
            s6_envdir,
            self.paths.env_dir,
            subproc.resolve('s6_svscan'),
            self.paths.svscan_tree_dir
        ])
