"""Implementation of cron API.
"""

import fnmatch
import logging
import re

from treadmill import authz
from treadmill import context
from treadmill import cron
from treadmill import exc
from treadmill import schema

_LOGGER = logging.getLogger(__name__)

CRON_MODULE = 'treadmill.cron'


def app_start(job_id, event_type, resource, count):
    """App start event type"""
    if count is None:
        raise exc.InvalidInputError(
            __name__,
            'You must supply a count for {}'.format(event_type),
        )

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
        raise exc.InvalidInputError(
            __name__,
            'You must supply a count for {}'.format(event_type),
        )

    event, action = event_type.split(':')
    job_name = '{}:event={}:action={}:count={}'.format(
        resource, event, action, count
    )

    func_kwargs = dict(
        monitor_name=resource,
        count=count,
    )
    return job_name, func_kwargs


def update_job(scheduler, job_id, event, resource, expression, count):
    """Update a cron job"""
    func = '{}.{}'.format(CRON_MODULE, event)

    event_func = re.sub(':', '_', event)
    event_func = re.sub('-', '_', event_func)

    job_name, func_kwargs = globals()[event_func](
        job_id, event, resource, count
    )

    trigger_args = cron.cron_to_dict(expression)

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
        replace_existing=True,
        misfire_grace_time=cron.ONE_DAY_IN_SECS,
        kwargs=func_kwargs,
        **trigger_args
    )

    return job


class API(object):
    """Treadmill Cron REST api."""

    def __init__(self):
        self.scheduler = None

        def scheduler():
            """Lazily get scheduler"""
            if self.scheduler:
                return self.scheduler

            zkclient = context.GLOBAL.zk.conn
            self.scheduler = cron.get_scheduler(zkclient)

            return self.scheduler

        def _list(match=None):
            """List configured instances."""
            if match is None:
                match = '*'

            jobs = scheduler().get_jobs()
            _LOGGER.debug('jobs: %r', jobs)

            filtered = [
                cron.job_to_dict(job)
                for job in jobs
                if fnmatch.fnmatch(job.id, match)
            ]
            return sorted(filtered)

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def get(rsrc_id):
            """Get instance configuration."""
            job = cron.get_job(scheduler(), rsrc_id)
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/resource'},
                       {'$ref': 'cron.json#/verbs/create'}]},
        )
        def create(rsrc_id, rsrc):
            """Create (configure) instance."""
            _LOGGER.info('create: %s %r', rsrc_id, rsrc)

            job = cron.get_job(scheduler(), rsrc_id)
            if job:
                raise exc.FoundError('{} already exists'.format(rsrc_id))

            event = rsrc.get('event')
            resource = rsrc.get('resource')
            expression = rsrc.get('expression')
            count = rsrc.get('count')

            job = update_job(
                scheduler(), rsrc_id, event, resource, expression, count
            )
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update instance configuration."""
            _LOGGER.info('update: %s %r', rsrc_id, rsrc)

            event = rsrc.get('event')
            resource = rsrc.get('resource')
            expression = rsrc.get('expression')
            count = rsrc.get('count')

            job = update_job(
                scheduler(), rsrc_id, event, resource, expression, count
            )
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured instance."""
            _LOGGER.info('delete: %s', rsrc_id)

            job = cron.get_job(scheduler(), rsrc_id)
            _LOGGER.debug('job: %r', job)

            if job:
                _LOGGER.info('Removing job %s', rsrc_id)
                job.remove()

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
