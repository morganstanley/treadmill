"""
Cron model for an app.
"""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import cron
from treadmill import exc
from treadmill.cron import run as cron_exec

_LOGGER = logging.getLogger(__name__)


def create(scheduler, job_id, event, action, resource, expression, count):
    """Create a new job/model"""
    func = '{}.{}:{}'.format(cron_exec.CRON_EXEC_MODULE, event, action)

    job_name, func_kwargs = globals()[action](
        job_id, event, action, resource, count
    )

    trigger_args = cron.cron_to_dict(expression)

    return cron.create_job(
        scheduler, job_id, job_name, func, func_kwargs, trigger_args
    )


def update(scheduler, job_id, event, action, resource, expression, count):
    """Update a job/model"""
    func = '{}.{}:{}'.format(cron_exec.CRON_EXEC_MODULE, event, action)

    job_name, func_kwargs = globals()[action](
        job_id, event, action, resource, count
    )

    trigger_args = cron.cron_to_dict(expression)

    return cron.update_job(
        scheduler, job_id, job_name, func, func_kwargs, trigger_args
    )


def start(job_id, event, action, resource, count):
    """App start event type"""
    if count is None:
        raise exc.InvalidInputError(
            __name__,
            'You must supply a count for {}:{}'.format(event, action),
        )

    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        job_id=job_id,
        app_name=resource,
        count=count,
    )
    return job_name, func_kwargs


def stop(job_id, event, action, resource, _count):
    """App stop event type"""
    job_name = '{}:event={}:action={}'.format(
        resource, event, action
    )

    func_kwargs = dict(
        job_id=job_id,
        app_name=resource,
    )
    return job_name, func_kwargs
