"""
Treadmill admin cron CLI tools.
"""
from __future__ import absolute_import

import logging
import re

import click

import pytz

from apscheduler.jobstores import base

from treadmill import cli
from treadmill import context
from treadmill import cron

_LOGGER = logging.getLogger(__name__)
_EVENT_MODULE = 'treadmill.cron'

_FORMATTER = cli.make_formatter(cli.CronPrettyFormatter)

ON_EXCEPTIONS = cli.handle_exceptions([
    (base.JobLookupError, None),
    (pytz.UnknownTimeZoneError, 'Unknown timezone'),
])


def app_start(job_id, event_type, resource, count):
    """App start event type"""
    if count is None:
        cli.bad_exit('You must supply a count for %s', event_type)

    event, action = event_type.split(':')
    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        job_id=job_id,
        app_name=resource,
        count=count,
    )
    return job_name, func_kwargs


def app_stop(job_id, event_type, resource, count):
    """App stop event type"""
    event, action = event_type.split(':')
    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        job_id=job_id,
        app_name=resource,
    )
    return job_name, func_kwargs


def monitor_set_count(_job_id, event_type, resource, count):
    """Monitor set count event type"""
    if count is None:
        cli.bad_exit('You must supply a count for %s', event_type)

    event, action = event_type.split(':')
    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        monitor_name=resource,
        count=count,
    )
    return job_name, func_kwargs


def init():
    """Return top level command handler."""
    ctx = {}

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def cron_group():
        """Manage Treadmill cron jobs"""
        zkclient = context.GLOBAL.zk.conn
        ctx['scheduler'] = cron.get_scheduler(zkclient)

    @cron_group.command()
    @click.argument('job_id')
    @click.argument('event',
                    type=click.Choice([
                        'app:start', 'app:stop', 'monitor:set_count'
                    ]))
    @click.option('--resource',
                  help='The resource to schedule, e.g. an app name',
                  required=True)
    @click.option('--expression', help='The cron expression for scheduling',
                  required=True)
    @click.option('--count', help='The number of instances to start',
                  type=int)
    @ON_EXCEPTIONS
    def configure(job_id, event, resource, expression, count):
        """Create or modify an existing app start schedule"""
        func = '{}.{}'.format(_EVENT_MODULE, event)

        event_func = re.sub(':', '_', event)
        job_name, func_kwargs = globals()[event_func](
            job_id, event, resource, count
        )

        trigger_args = cron.cron_to_dict(expression)

        scheduler = ctx['scheduler']
        _LOGGER.debug('scheduler: %r', scheduler)

        job = cron.get_job(scheduler, job_id)
        if job:
            _LOGGER.info('Removing job %s', job_id)
            job.remove()

        _LOGGER.info('Adding job %s', job_id)
        job = scheduler.add_job(
            func,
            trigger='cron',
            id=job_id,
            name=job_name,
            misfire_grace_time=cron.ONE_DAY_IN_SECS,
            kwargs=func_kwargs,
            **trigger_args
        )

        cli.out(_FORMATTER(cron.job_to_dict(job)))

    @cron_group.command(name='list')
    def _list():
        """List out all cron events"""
        scheduler = ctx['scheduler']

        jobs = scheduler.get_jobs()

        job_dicts = [cron.job_to_dict(job) for job in jobs]
        _LOGGER.debug('job_dicts: %r', jobs)

        cli.out(_FORMATTER(job_dicts))

    @cron_group.command()
    @click.argument('job_id')
    @ON_EXCEPTIONS
    def delete(job_id):
        """Delete an app schedule"""
        scheduler = ctx['scheduler']

        _LOGGER.info('Removing job %s', job_id)
        scheduler.remove_job(job_id)

    del configure
    del _list
    del delete

    return cron_group
