"""Treadmill schedule application event.

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


def stop(job_id=None, app_name=None):
    """Stop an application"""
    _LOGGER.debug('job_id: %s, app_name: %r', job_id, app_name)

    try:
        response = restclient.get(
            [_API_URL],
            '/instance/?match={}'.format(app_name)
        )
        instances = response.json().get('instances', [])
        _LOGGER.info('Stopping: %r', instances)

        if not instances:
            _LOGGER.warning('No instances running for %s', app_name)
            return

        restclient.post(
            [_API_URL],
            '/instance/_bulk/delete',
            payload=dict(instances=instances),
            headers={'X-Treadmill-Trusted-Agent': 'cron'}
        )
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Error stopping app: %s', app_name)


def start(job_id=None, app_name=None, count=1):
    """Start an application in the given cell"""
    _LOGGER.debug('job_id: %s, app_name: %s, count: %s',
                  job_id, app_name, count)

    if not app_name:
        _LOGGER.error('No app name provided, cannot continue')
        return

    try:
        restclient.post(
            [_API_URL],
            '/instance/{}?count={}'.format(app_name, count),
            payload={},
            headers={'X-Treadmill-Trusted-Agent': 'cron'}
        )
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Error starting app: %s', app_name)
