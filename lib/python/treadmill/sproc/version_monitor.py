"""Treadmill version monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click
import pkg_resources

from treadmill import context
from treadmill import plugin_manager
from treadmill import sysinfo
from treadmill import zkutils
from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)

# Number of previous versions of each server to save.
_MAX_VERSIONS = 20

_TREADMILL_DIST_PREFIX = 'Treadmill'


def _save_version(zkclient, hostname, version):
    """Save server version data to ZK.
    """
    version_path = z.path.version(hostname)
    zkutils.put(zkclient, version_path, version)

    version_history_path = z.path.version_history(hostname)
    versions = zkutils.get_default(zkclient, version_history_path)
    if not versions:
        versions = []
    versions.insert(0, version)
    zkutils.put(zkclient, version_history_path, versions[0:_MAX_VERSIONS])


def init():
    """Top level command handler."""

    @click.command()
    def version_monitor():
        """Runs node version monitor."""
        _LOGGER.info('Initializing version monitor')

        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_lost)

        while (not zkclient.exists(z.VERSION) or
               not zkclient.exists(z.VERSION_HISTORY)):
            _LOGGER.warning('namespace not ready.')
            time.sleep(30)

        hostname = sysinfo.hostname()

        distributions = {
            dist.project_name: dist.version
            for dist in iter(pkg_resources.working_set)
            if dist.project_name.startswith(_TREADMILL_DIST_PREFIX)
        }

        version = {
            'distributions': distributions,
            'since': int(time.time())
        }

        for name in plugin_manager.names('treadmill.version_monitor'):
            plugin = plugin_manager.load('treadmill.version_monitor', name)
            version.update(plugin())

        _save_version(zkclient, hostname, version)

        while True:
            time.sleep(100000)

        _LOGGER.info('service shutdown.')

    return version_monitor
