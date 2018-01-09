"""Treadmill admin cron CLI tools.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
import pytz

from apscheduler.jobstores import base

from treadmill import cli
from treadmill import context
from treadmill import cron
from treadmill import exc

from treadmill.cron import model as cron_model


_LOGGER = logging.getLogger(__name__)

_FORMATTER = cli.make_formatter('cron')

ON_EXCEPTIONS = cli.handle_exceptions([
    (exc.InvalidInputError, None),
    (base.JobLookupError, None),
    (pytz.UnknownTimeZoneError, 'Unknown timezone'),
])


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
    @click.argument('event')
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
        scheduler = ctx['scheduler']

        job = None
        try:
            job = cron_model.create(
                scheduler, job_id, event, resource, expression, count
            )
        except exc.FoundError:
            job = cron_model.update(
                scheduler, job_id, event, resource, expression, count
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

    @cron_group.command()
    @click.argument('job_id')
    @ON_EXCEPTIONS
    def pause(job_id):
        """Pause a job ID"""
        scheduler = ctx['scheduler']

        _LOGGER.info('Pause job %s', job_id)
        scheduler.pause_job(job_id)

    @cron_group.command()
    @click.argument('job_id')
    @ON_EXCEPTIONS
    def resume(job_id):
        """Resume a job ID"""
        scheduler = ctx['scheduler']

        _LOGGER.info('Resume job %s', job_id)
        scheduler.resume_job(job_id)

    del configure
    del _list
    del delete
    del pause
    del resume

    return cron_group
