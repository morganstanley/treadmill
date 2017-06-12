"""
Model of cron job.
"""

import importlib
import logging
import re

from treadmill import exc

_LOGGER = logging.getLogger(__name__)


def _get_model_module(model):
    """Get an importlib module based on the model"""
    try:
        model_module = re.sub('-', '_', model)
        return importlib.import_module(
            'treadmill.cron.model.{}'.format(model_module)
        )
    except ImportError as err:
        raise exc.NotFound('{} cron model is not available: {}'.format(
            model, err
        ))


def create(scheduler, job_id, event, resource, expression, count):
    """Create a new job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = _get_model_module(model)
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.create(
        scheduler, job_id, model, action, resource, expression, count
    )


def update(scheduler, job_id, event, resource, expression, count):
    """Update a job/model"""
    model, action = event.split(':')
    _LOGGER.debug('model: %s, action: %s', model, action)

    model_module = _get_model_module(model)
    _LOGGER.debug('model_module: %r', model_module)

    return model_module.update(
        scheduler, job_id, model, action, resource, expression, count
    )
