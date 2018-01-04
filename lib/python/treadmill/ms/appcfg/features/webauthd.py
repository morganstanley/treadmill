"""Configures webauthd inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import logging

from treadmill.appcfg.features import feature_base

_LOGGER = logging.getLogger(__name__)


class WebAuthdFeature(feature_base.Feature):
    """webauthd manifest feature."""

    def applies(self, manifest, runtime):
        return runtime == 'linux'

    def configure(self, manifest):
        _LOGGER.info('Configuring webauthd.')
        webauthd_svc = {
            'name': 'webauthd',
            # TODO: we need to rationalize proid: root vs root: True. Currently
            #       appcfmg/manifest requires root: True, and some other code
            #       seem to use 'proid' property.
            'proid': 'root',
            'root': True,
            'restart': {
                'limit': 5,
                'interval': 60,
            },
            'command': '${TREADMILL}/sbin/run_webauthd',
            'environ': [],
            'config': None,
            'downed': False,
            'trace': False,
        }
        manifest['services'].append(webauthd_svc)
