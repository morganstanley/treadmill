"""
Cron model for a monitor.


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

This module is responsible for creating the job (or model) in the scheduler.
"""
from __future__ import absolute_import

import logging
import re

from treadmill import cron
from treadmill import exc
from treadmill.cron import run as cron_exec

_LOGGER = logging.getLogger(__name__)


def create(scheduler, job_id, event, action, resource, expression, count):
    """Create a new job/model"""
    action_func = re.sub('-', '_', action)

    func = '{}.{}:{}'.format(cron_exec.CRON_EXEC_MODULE, event, action_func)

    job_name, func_kwargs = globals()[action_func](
        event, action, resource, count
    )

    trigger_args = cron.cron_to_dict(expression)

    return cron.create_job(
        scheduler, job_id, job_name, func, func_kwargs, trigger_args
    )


def update(scheduler, job_id, event, action, resource, expression, count):
    """Update a job/model"""
    action_func = re.sub('-', '_', action)

    func = '{}.{}:{}'.format(cron_exec.CRON_EXEC_MODULE, event, action_func)

    job_name, func_kwargs = globals()[action_func](
        event, action, resource, count
    )

    trigger_args = cron.cron_to_dict(expression)

    return cron.update_job(
        scheduler, job_id, job_name, func, func_kwargs, trigger_args
    )


def set_count(event, action, resource, count):
    """Monitor set count event type"""
    if count is None:
        raise exc.InvalidInputError(
            __name__,
            'You must supply a count for {}'.format(event),
        )

    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        monitor_name=resource,
        count=count,
    )
    return job_name, func_kwargs
