"""Helper module to manage Treadmill versions.
"""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time

import pkg_resources

from treadmill import plugin_manager
from treadmill import zkutils
from treadmill import zknamespace as z

# Number of previous versions of each server to save.
_MAX_VERSIONS = 20

_TREADMILL_DIST_PREFIX = 'Treadmill'


def get_version():
    """Get server version data.
    """
    distributions = {
        dist.project_name: dist.version
        for dist in iter(pkg_resources.working_set)
        if dist.project_name.startswith(_TREADMILL_DIST_PREFIX)
    }

    version = {
        'distributions': distributions,
        'since': int(time.time())
    }

    for name in plugin_manager.names('treadmill.version'):
        plugin = plugin_manager.load('treadmill.version', name)
        version.update(plugin())

    return version


def save_version(zkclient, hostname, version):
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
