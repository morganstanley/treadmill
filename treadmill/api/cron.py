"""Implementation of cron API.
"""

import fnmatch
import logging

from treadmill import authz
from treadmill import context
from treadmill import cron
from treadmill import schema
from treadmill.cron import model as cron_model

_LOGGER = logging.getLogger(__name__)


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

            event = rsrc.get('event')
            resource = rsrc.get('resource')
            expression = rsrc.get('expression')
            count = rsrc.get('count')

            job = cron_model.create(
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

            job = cron_model.update(
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
        self.scheduler = scheduler


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
