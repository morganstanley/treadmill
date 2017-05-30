"""
Treadmill schedule application event.

This module allows the treadmill cron to take actions on applications,
for example, start and stop them at a given time.
"""

import logging
import importlib
import fnmatch

from treadmill import admin
from treadmill import context
from treadmill import master
from treadmill import cron

_LOGGER = logging.getLogger(__name__)


def stop(job_id=None, app_name=None):
    """Stop an application"""
    _LOGGER.debug('app_name: %r', app_name)
    _LOGGER.debug('job_id: %s', job_id)

    zkclient = context.GLOBAL.zk.conn

    instances = master.list_scheduled_apps(zkclient)

    app_name_pattern = '{}*'.format(app_name)
    filtered = [
        inst for inst in instances
        if fnmatch.fnmatch(inst, app_name_pattern)
    ]

    if not filtered:
        _LOGGER.info('Nothing is running for %s', app_name)
        return

    _LOGGER.info('Stopping all instances: %r', filtered)
    master.delete_apps(zkclient, filtered)


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

    admin_app = admin.Application(context.GLOBAL.ldap.conn)

    configured = admin_app.get(app_name)

    if not configured:
        _LOGGER.info(
            'App %s is not configured, pausing job %s', app_name, job.id
        )
        job.pause()
        return

    instance_plugin = None
    try:
        instance_plugin = importlib.import_module(
            'treadmill.plugins.api.instance')
    except ImportError as err:
        _LOGGER.info('Unable to load auth plugin: %s', err)

    if instance_plugin:
        configured = instance_plugin.add_attributes(
            app_name, configured
        )

    if 'identity_group' not in configured:
        configured['identity_group'] = None

    if 'affinity' not in configured:
        configured['affinity'] = '{0}.{1}'.format(*app_name.split('.'))

    if '_id' in configured:
        del configured['_id']
    _LOGGER.info('Configured: %s %r', app_name, configured)

    scheduled = master.create_apps(
        zkclient, app_name, configured, count
    )
    _LOGGER.debug('scheduled: %r', scheduled)
