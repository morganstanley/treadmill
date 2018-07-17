"""Implementation of cron API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import logging

from treadmill import context
from treadmill import cron
from treadmill import schema
from treadmill.cron import model as cron_model

_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill CRON REST api."""

    def __init__(self):

        def _scheduler():
            """Lazily get scheduler"""

            zkclient = context.GLOBAL.zk.conn
            return cron.get_scheduler(zkclient)

        def _list(match=None, resource=None):
            """List configured cron jobs."""
            jobs = _scheduler().get_jobs()
            _LOGGER.debug('jobs: %r', jobs)

            filtered = []
            for job_obj in jobs:
                job = cron.job_to_dict(job_obj)
                if not match and not resource:
                    filtered.append(job)
                    continue
                if match and fnmatch.fnmatch(job['_id'], match):
                    filtered.append(job)
                if resource and fnmatch.fnmatch(job['resource'], resource):
                    filtered.append(job)

            return sorted(filtered, key=lambda item: item['_id'])

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def get(rsrc_id):
            """Get cron job configuration."""
            job = cron.get_job(_scheduler(), rsrc_id)
            _LOGGER.debug('job: %r', job)

            if job is None:
                return job

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
            {'allOf': [{'$ref': 'cron.json#/verbs/update'}]},
            pause={'$ref': 'cron.json#/pause'},
            resume={'$ref': 'cron.json#/resume'},
        )
        def update(rsrc_id, rsrc, pause=False, resume=False):
            """Update cron job configuration."""
            _LOGGER.info('update: %s %r', rsrc_id, rsrc)

            if pause:
                job = _scheduler().pause_job(rsrc_id)
                return cron.job_to_dict(job)

            if resume:
                job = _scheduler().resume_job(rsrc_id)
                return cron.job_to_dict(job)

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
