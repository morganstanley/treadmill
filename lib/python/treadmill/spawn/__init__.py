"""Treadmill spawn extension.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

BUCKETS = 256
MAX_PER_BUCKET = 1000

APPS_DIR = 'apps'
SVSCAN_TREE_DIR = os.path.join(APPS_DIR, 'svscan_tree')
JOBS_DIR = os.path.join(APPS_DIR, 'jobs')
MANIFEST_DIR = 'manifest'
RUNNING_DIR = 'running'
CLEANUP_DIR = 'cleanup'
ZK_MIRROR_DIR = 'zk_mirror'
CELLAPI_SOCK = 'cellapi.sock'

JOB_DATA_DIR = 'data'
JOB_FINISH_TIMEOUT = 0


class SpawnPaths:
    """Treadmill spawn manifest watch."""

    __slots__ = (
        'root',
        'jobs_dir',
        'manifest_dir',
        'running_dir',
        'cleanup_dir',
        'zk_mirror_dir',
        'cellapi_sock',
        'svscan_tree_dir',
        'buckets',
        'env_dir'
    )

    def __init__(self, root, buckets=BUCKETS):
        self.root = root
        self.buckets = buckets
        self.jobs_dir = os.path.join(self.root, JOBS_DIR)
        self.manifest_dir = os.path.join(self.root, MANIFEST_DIR)
        self.running_dir = os.path.join(self.root, RUNNING_DIR)
        self.cleanup_dir = os.path.join(self.root, CLEANUP_DIR)
        self.cellapi_sock = os.path.join(self.root, CELLAPI_SOCK)
        self.zk_mirror_dir = os.path.join(self.root, ZK_MIRROR_DIR)
        self.svscan_tree_dir = os.path.join(self.root, SVSCAN_TREE_DIR)
        self.env_dir = os.path.join(self.svscan_tree_dir, '.s6-svscan', 'env')
