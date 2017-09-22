"""Treadmill schedule monitor event.

This module allows the treadmill cron to take actions on applications,
for example, start and stop them at a given time.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import restclient

_LOGGER = logging.getLogger(__name__)


# TODO: this is hack, as this should be pass as option from cron sproc
#       command line. I was not able to figure out how to pass context from
#       cron/scheduler to the callback.
_API_URL = 'http+unix://%2Ftmp%2Fcellapi.sock'


def set_count(monitor_name=None, count=None):
    """Set the count on the supplied monitor"""
    _LOGGER.debug('monitor: %s, count: %s', monitor_name, count)

    if not monitor_name:
        _LOGGER.error('No monitor name supplied, cannot continue')
        return

    restclient.post(
        [_API_URL],
        '/app-monitor/{}'.format(monitor_name),
        payload={'count': count},
        headers={'X-Treadmill-Trusted-Agent': 'cron'}
    )
