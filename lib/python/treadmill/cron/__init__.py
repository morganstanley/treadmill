"""High level cron API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from apscheduler.jobstores import base
from apscheduler.jobstores import zookeeper
from apscheduler.schedulers import twisted

from treadmill import exc
from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)

ONE_DAY_IN_SECS = 60 * 60 * 24

CRON_MODULE = 'treadmill.cron'

_FIELD_NAMES = [
    'second', 'minute', 'hour', 'day', 'month', 'day_of_week', 'year'
]
_FIELD_POS = dict((field, i) for i, field in enumerate(_FIELD_NAMES))

_SCHEDULER = None


def get_scheduler(zkclient):
    """Get scheduler"""
    global _SCHEDULER  # pylint: disable=W0603

    if not _SCHEDULER:

        _SCHEDULER = twisted.TwistedScheduler()
        zk_jobstore = zookeeper.ZooKeeperJobStore(
            path=z.CRON_JOBS,
            client=zkclient
        )

        _SCHEDULER.add_jobstore(zk_jobstore)
        _SCHEDULER.start()

    return _SCHEDULER


def cron_to_dict(cron):
    """Get trigger args from a cron expression"""
    cexpression = cron.split(' ')
    _LOGGER.debug('cexpression: %r', cexpression)

    trigger_args = {}
    if len(cexpression) > 0:
        trigger_args['second'] = cexpression[0]
    if len(cexpression) > 1:
        trigger_args['minute'] = cexpression[1]
    if len(cexpression) > 2:
        trigger_args['hour'] = cexpression[2]
    if len(cexpression) > 3:
        trigger_args['day'] = cexpression[3]
    if len(cexpression) > 4:
        trigger_args['month'] = cexpression[4]
    if len(cexpression) > 5:
        trigger_args['day_of_week'] = cexpression[5]
    if len(cexpression) > 6:
        trigger_args['year'] = cexpression[6]
    if len(cexpression) > 7:
        value = cexpression[7]
        if value == '*':
            raise exc.InvalidInputError(
                __name__,
                'TimeZone can not be "*"',
            )

        trigger_args['timezone'] = cexpression[7]
    _LOGGER.debug('trigger_args: %r', trigger_args)

    return trigger_args


def cron_expression(trigger):
    """Get a cron expression from the given trigger"""
    _LOGGER.debug('trigger.fields: %r', trigger.fields)
    # Need to loop through, as it is an array and not in the same Cron
    # expression order, thus we need to insert into the proper order.
    fields = ['*'] * len(_FIELD_NAMES)
    for field in trigger.fields:
        try:
            fields[_FIELD_POS[field.name]] = str(field)
        except KeyError:
            pass

    _LOGGER.debug('fields: %r', fields)

    return ' '.join(fields)


def job_to_dict(job):
    """Convert job to dict"""
    trigger = job.trigger
    id_details = job.name.split(':')
    resource = id_details.pop(0)

    job_dict = dict(
        _id=job.id,
        name=job.name,
        resource=resource,
        expression=cron_expression(trigger),
        next_run_time=job.next_run_time,
        timezone=trigger.timezone,
    )

    for key_value in id_details[::1]:
        key, value = key_value.split('=')
        job_dict[key] = value

    return job_dict


def get_job(scheduler, job_id):
    """Get a job given a job_id, if none, return None"""
    try:
        return scheduler.get_job(job_id)
    except base.JobLookupError:
        return None


def create_job(scheduler, job_id, job_name, func, func_kwargs, trigger_args):
    """Create a new job/model"""
    _LOGGER.debug(
        'job_id: %s, job_name: %s, func: %s, func_kwargs: %r, trigger_args: '
        '%r', job_id, job_name, func, func_kwargs, trigger_args
    )

    job = get_job(scheduler, job_id)
    if job:
        raise exc.FoundError('{} already exists'.format(job_id))

    _LOGGER.info('Adding job %s', job_id)
    job = scheduler.add_job(
        func,
        trigger='cron',
        id=job_id,
        name=job_name,
        misfire_grace_time=ONE_DAY_IN_SECS,
        kwargs=func_kwargs,
        **trigger_args
    )

    return job


def update_job(scheduler, job_id, job_name, func, func_kwargs, trigger_args):
    """Update an existing job/model"""
    _LOGGER.debug(
        'job_id: %s, job_name: %s, func: %s, func_kwargs: %r, trigger_args: '
        '%r', job_id, job_name, func, func_kwargs, trigger_args
    )

    job = get_job(scheduler, job_id)
    if not job:
        raise exc.NotFoundError('{} does not exist'.format(job_id))

    _LOGGER.info('Updating job %s', job_id)
    job = scheduler.add_job(
        func,
        trigger='cron',
        id=job_id,
        name=job_name,
        replace_existing=True,
        misfire_grace_time=ONE_DAY_IN_SECS,
        kwargs=func_kwargs,
        **trigger_args
    )

    return job
