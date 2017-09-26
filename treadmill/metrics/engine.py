""" Cgroups read engine to read the cgroups data periodically
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os
import threading
import time


from treadmill import appenv
from treadmill import exc
from treadmill import fs
from treadmill import metrics

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


class CgroupReader(object):
    """Cgroup reader engine to spawn new thread to read cgroup periodically
    """

    def __init__(self, approot, interval):
        self.cache = {'treadmill': {}, 'core': {}, 'app': {}}
        self._interval = interval

        self._tm_env = appenv.AppEnvironment(root=approot)
        self._sys_svcs = _sys_svcs(approot)
        # TODO: sys_maj_min will be used changing treadmill.metrics.app_metrics
        self._sys_maj_min = '{}:{}'.format(*fs.path_to_maj_min(approot))
        self._sys_block_dev = fs.maj_min_to_blk(*fs.path_to_maj_min(approot))

        # if interval is zero, we just read one time
        if interval <= 0:
            self._read()
        else:
            self._loop()

    def get(self, cgrp_name):
        """Get a cgroup data"""
        (data_type, cgrp) = cgrp_name.split('.', 1)

        return self.cache[data_type][cgrp]

    def snapshot(self):
        """Get all cgroups data in cache"""
        return self.cache

    def list(self):
        """Get all cgroups item name in a  list"""
        return (
            ['treadmill.{}'.format(cgrp)
             for cgrp in self.cache['treadmill'].keys()] +
            ['core.{}'.format(cgrp) for cgrp in self.cache['core'].keys()] +
            ['app.{}'.format(cgrp) for cgrp in self.cache['app'].keys()]
        )

    def _loop(self):
        before = time.time()
        self._read()
        now = time.time()
        next_wait = int(self._interval + before - now)
        # should not happen as it means _read() lasting too much time
        if next_wait < 0:
            next_wait = 0

        threading.Timer(next_wait, self._loop).start()

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

    def _read(self):
        _LOGGER.info("start reading cgroups")
        sys_block_dev = self._sys_block_dev

        for cgrp in CORE_GROUPS:
            if cgrp == 'treadmill':
                self.cache['treadmill'][cgrp] = metrics.app_metrics(
                    cgrp, sys_block_dev
                )
            else:
                core_cgrp = os.path.join('treadmill', cgrp)
                self.cache['treadmill'][cgrp] = metrics.app_metrics(
                    core_cgrp, None
                )

        for svc in self._sys_svcs:
            svc_cgrp = os.path.join('treadmill', 'core', svc)
            self.cache['core'][svc] = metrics.app_metrics(
                svc_cgrp, None
            )

        seen_apps = set()
        for app_dir in glob.glob('%s/*' % self._tm_env.apps_dir):
            if not os.path.isdir(app_dir):
                continue

            app_unique_name = os.path.basename(app_dir)
            seen_apps.add(app_unique_name)
            (block_dev, _blkio_major_minor) = self._get_block_dev_version(
                app_unique_name
            )
            app_cgrp = os.path.join('treadmill', 'apps', app_unique_name)
            self.cache['app'][app_unique_name] = metrics.app_metrics(
                app_cgrp, block_dev
            )

        # Removed metrics for apps that are not present anymore
        for cgrp in set(self.cache['app']) - seen_apps:
            del self.cache['app'][cgrp]

        _LOGGER.info(
            "%d core services, %d containers in cache",
            len(self.cache['core']), len(self.cache['app'])
        )
