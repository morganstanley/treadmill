"""
Treadmill schedule application event.

This module allows the treadmill cron to take actions on applications,
for example, start and stop them at a given time.
"""

import logging

from treadmill import authz
from treadmill import context
from treadmill import cron
from treadmill.api import instance

_LOGGER = logging.getLogger(__name__)


def stop(job_id=None, app_name=None):
    """Stop an application"""
    _LOGGER.debug('app_name: %r', app_name)
    _LOGGER.debug('job_id: %s', job_id)

    instance_api = instance.init(authz.NullAuthorizer())

    instances = instance_api.list(match=app_name)
    _LOGGER.info('Stopping: %r', instances)
    for instance_id in instances:
        instance_api.delete(instance_id, deleted_by='cron')


def start(job_id=None, app_name=None, count=1):
    """Start an application in the given cell"""
    _LOGGER.debug('app_name: %s', app_name)
    _LOGGER.debug('job_id: %s', job_id)
    _LOGGER.debug('count: %s', count)

    zkclient = context.GLOBAL.zk.conn
    scheduler = cron.get_scheduler(zkclient)

    job = scheduler.get_job(job_id)

    if not app_name:
        _LOGGER.error('No app name provided, cannot continue')
        return

    instance_api = instance.init(authz.NullAuthorizer())
    try:
        scheduled = instance_api.create(
            app_name, {}, count=count, created_by='cron'
        )
        _LOGGER.debug('scheduled: %r', scheduled)

    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Unable to create instances: %s', app_name)
        job.pause()
