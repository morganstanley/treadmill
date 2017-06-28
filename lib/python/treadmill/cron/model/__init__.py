"""
Model of cron job.
"""

import logging
import re

from treadmill import exc
from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_CRON_MODULES = plugin_manager.extensions('treadmill.cron')


def create(scheduler, job_id, event, resource, expression, count):
    """Create a new job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = _CRON_MODULES()[model].plugin
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.create(
        scheduler, job_id, model, action, resource, expression, count
    )


def update(scheduler, job_id, event, resource, expression, count):
    """Update a job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = _CRON_MODULES()[model].plugin
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.update(
        scheduler, job_id, model, action, resource, expression, count
    )
