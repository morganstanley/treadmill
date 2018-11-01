"""Configures warpgate inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill.appcfg.features import feature_base


_LOGGER = logging.getLogger(__name__)


class WarpgateFeature(feature_base.Feature):
    """Feature to enable warpgate daemon in container
    """

    def applies(self, manifest, runtime):
        return runtime == 'linux'

    def configure(self, manifest):
        _LOGGER.info('Configuring warpgate.')

        manifest['system_services'].append(
            _generate_warpgate_service()
        )
        manifest['warpgate'] = True


def _generate_warpgate_service():

    # full command include creating rest module cfg file and launch sproc
    cmd = 'exec $TREADMILL/bin/treadmill sproc warpgate'

    return {
        'name': 'warpgate',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': cmd,
        'root': True,
        'environ': [
            {
                'name': 'KRB5CCNAME',
                'value': os.path.expandvars(
                    'FILE:${TREADMILL_HOST_TICKET}'
                ),
            },
        ],
        'config': None,
        'downed': False,
        'trace': False,
    }
