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
    """Treadmill CRON REST api."""

    def __init__(self):

        def _scheduler():
            """Lazily get scheduler"""

            zkclient = context.GLOBAL.zk.conn
            return cron.get_scheduler(zkclient)

        def _list(match=None):
            """List configured cron jobs."""
            if match is None:
                match = '*'

            jobs = _scheduler().get_jobs()
            _LOGGER.debug('jobs: %r', jobs)

            filtered = [
                cron.job_to_dict(job)
                for job in jobs
                if fnmatch.fnmatch(job.id, match)
            ]
            return sorted(filtered)

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def get(rsrc_id):
            """Get cron job configuration."""
            job = cron.get_job(_scheduler(), rsrc_id)
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/resource'},
                       {'$ref': 'cron.json#/verbs/create'}]},
        )
        def create(rsrc_id, rsrc):
            """Create cron job."""
            _LOGGER.info('create: %s %r', rsrc_id, rsrc)

            event = rsrc.get('event')
            resource = rsrc.get('resource')
            expression = rsrc.get('expression')
            count = rsrc.get('count')

            job = cron_model.create(
                _scheduler(), rsrc_id, event, resource, expression, count
            )
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update cron job configuration."""
            _LOGGER.info('update: %s %r', rsrc_id, rsrc)

            event = rsrc.get('event')
            resource = rsrc.get('resource')
            expression = rsrc.get('expression')
            count = rsrc.get('count')

            job = cron_model.update(
                _scheduler(), rsrc_id, event, resource, expression, count
            )
            _LOGGER.debug('job: %r', job)

            return cron.job_to_dict(job)

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured cron job."""
            _LOGGER.info('delete: %s', rsrc_id)

            job = cron.get_job(_scheduler(), rsrc_id)
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
