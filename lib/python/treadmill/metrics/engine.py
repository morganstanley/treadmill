""" Cgroups read engine to read the cgroups data periodically
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os

from treadmill import appenv
from treadmill import cgutils
from treadmill import exc
from treadmill import metrics

from treadmill.fs import linux as fs_linux

CORE_GROUPS = [
    'apps',
    'core',
    'treadmill'
]


_LOGGER = logging.getLogger(__name__)


def _sys_svcs(root_dir):
    """Contructs list of system services."""
    return sorted([
        os.path.basename(s)
        for s in glob.glob(os.path.join(root_dir, 'init', '*'))
        if not (s.endswith('.out') or s.endswith('.err'))])


def _read(path, *paths, block_dev=None):
    if paths:
        path = os.path.join(path, *paths)
    return metrics.app_metrics(path, block_dev)


class CgroupReader:
    """Cgroup reader engine to read cgroup
    """

    def __init__(self, approot, cgroup_prefix):
        self._approot = approot
        self._cgroup_prefix = cgroup_prefix
        # lazy load fields to prevent `treadmill.cli.admin.invoke` initializing
        # cgroup resources when `approot` is None
        self._initialized = {}

    @property
    def _tm_env(self):
        if '_tm_env' not in self._initialized:
            self._initialized['_tm_env'] = appenv.AppEnvironment(
                root=self._approot
            )
        return self._initialized['_tm_env']

    @property
    def _sys_svcs(self):
        if '_sys_svcs' not in self._initialized:
            self._initialized['_sys_svcs'] = _sys_svcs(self._approot)
        return self._initialized['_sys_svcs']

    @property
    def _sys_maj_min(self):
        # TODO: sys_maj_min will be used changing treadmill.metrics.app_metrics
        if '_sys_maj_min' not in self._initialized:
            self._initialized['_sys_maj_min'] = '{}:{}'.format(
                *fs_linux.maj_min_from_path(self._approot)
            )
        return self._initialized['_sys_maj_min']

    @property
    def _sys_block_dev(self):
        if '_sys_block_dev' not in self._initialized:
            self._initialized['_sys_block_dev'] = fs_linux.maj_min_to_blk(
                *fs_linux.maj_min_from_path(self._approot)
            )
        return self._initialized['_sys_block_dev']

    def _get_block_dev_version(self, app_unique_name):
        try:
            localdisk = self._tm_env.svc_localdisk.get(app_unique_name)
            blkio_major_minor = '{major}:{minor}'.format(
                major=localdisk['dev_major'],
                minor=localdisk['dev_minor'],
            )
            block_dev = localdisk['block_dev']
        except (exc.TreadmillError, IOError, OSError):
            blkio_major_minor = None
            block_dev = None

        return (block_dev, blkio_major_minor)

    def read_system(self, path, *paths):
        """Get aggregated system-level cgroup value."""
        # use configurable cgroup root for treadmill aggregated value
        if path == 'treadmill':
            path = self._cgroup_prefix
        return _read(path, *paths, block_dev=self._sys_block_dev)

    def read_service(self, svc):
        """Get treadmill core service cgroup value."""
        path = cgutils.core_group_name(self._cgroup_prefix)
        return _read(path, svc, block_dev=None)

    def read_services(self, detail=False):
        """Get all treadmill core service cgroup names.

        :param detail:
            if `True`, returns service's cgroup value along.
        """
        _LOGGER.info(
            'start reading core services cgroups with detail %s', detail
        )

        snapshot = {
            svc: self.read_service(svc) if detail else None
            for svc in self._sys_svcs
        }
        _LOGGER.info('%d core services', len(snapshot))
        return snapshot

    def read_app(self, name):
        """Get treadmill app cgroup value."""
        path = cgutils.apps_group_name(self._cgroup_prefix)
        (block_dev, _blkio_major_minor) = self._get_block_dev_version(name)
        return _read(path, name, block_dev=block_dev)

    def read_apps(self, detail=False):
        """Get all treadmill app cgroup names.

        :param detail:
            if `True`, returns app's cgroup value along.
        """
        _LOGGER.info('start reading apps cgroups with detail %s', detail)

        names = []
        for app_dir in glob.glob('%s/*' % self._tm_env.apps_dir):
            if not os.path.isdir(app_dir):
                continue
            name = os.path.basename(app_dir)
            names.append(name)

        snapshot = {
            name: self.read_app(name) if detail else None
            for name in names
        }
        _LOGGER.info('%d containers', len(snapshot))
        return snapshot
