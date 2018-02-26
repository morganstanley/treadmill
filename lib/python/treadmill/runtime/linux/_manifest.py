"""manifest module for linux runtime
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill.appcfg import manifest as app_manifest


_LOGGER = logging.getLogger(__name__)


def add_runtime(tm_env, manifest):
    """Adds linux runtime specific details to the manifest."""
    _transform_services(manifest)

    app_manifest.add_linux_system_services(tm_env, manifest)
    app_manifest.add_linux_services(manifest)


def _transform_services(manifest):
    # Normalize restart count
    manifest['services'] = [
        {
            'name': service['name'],
            'command': service['command'],
            'restart': {
                'limit': int(service['restart']['limit']),
                'interval': int(service['restart']['interval']),
            },
            'root': service.get('root', False),
            'proid': (
                'root' if service.get('root', False)
                else manifest['proid']
            ),
            'environ': manifest['environ'],
            'config': None,
            'downed': False,
            'trace': True,
            'logger': service.get('logger', 's6.app-logger.run'),
        }
        for service in manifest.get('services', [])
    ]
