"""Model of cron job.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)


def create(scheduler, job_id, event, resource, expression, count):
    """Create a new job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = plugin_manager.load('treadmill.cron', model)
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.create(
        scheduler, job_id, model, action, resource, expression, count
    )


def update(scheduler, job_id, event, resource, expression, count):
    """Update a job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = plugin_manager.load('treadmill.cron', model)
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.update(
        scheduler, job_id, model, action, resource, expression, count
    )
