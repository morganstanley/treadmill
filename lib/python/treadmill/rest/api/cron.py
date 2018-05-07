"""Treadmill cron REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import exc
from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for cron resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cron REST operations'
    )

    cron_model = {
        '_id': fields.String(description='Name'),
        'event': fields.String(description='Event type', enum=[
            'app:start', 'app:stop', 'monitor:set_count'
        ]),
        'resource': fields.String(description='Resource'),
        'expression': fields.String(description='Cron Expression'),
        'count': fields.Integer(description='Resource count', required=False),
    }
    req_model = api.model(
        'Cron', cron_model,
    )

    cron_resp_model = copy.copy(cron_model)
    cron_resp_model.update(
        action=fields.String(description='Action'),
        next_run_time=fields.DateTime(description='Next run time'),
        timezone=fields.String(description='Timezone'),
        event=fields.String(description='Event type', enum=[
            'app', 'monitor'
        ]),
    )

    resp_model = api.model(
        'CronResponse', cron_resp_model,
    )

    match_resource_parser = api.parser()
    match_resource_parser.add_argument(
        'match', help='A glob match on a job ID',
        location='args', required=False, default=None
    )
    match_resource_parser.add_argument(
        'resource', help='A glob match on a cron resource name',
        location='args', required=False, default=None
    )

    resume_pause_parser = api.parser()
    resume_pause_parser.add_argument(
        'resume', help='Resume a job ID',
        location='args', required=False, type=bool, default=False,
    )
    resume_pause_parser.add_argument(
        'pause', help='Pause a job ID',
        location='args', required=False, type=bool, default=False,
    )

    @namespace.route(
        '/',
    )
    class _CronList(restplus.Resource):
        """Treadmill Cron resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=resp_model,
                          parser=match_resource_parser)
        def get(self):
            """Returns list of configured cron."""
            args = match_resource_parser.parse_args()
            return impl.list(**args)

    @namespace.route('/<job_id>')
    @api.doc(params={'job_id': 'Cron ID/Name'})
    class _CronResource(restplus.Resource):
        """Treadmill Cron resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=resp_model)
        def get(self, job_id):
            """Return Treadmill cron configuration."""
            job = impl.get(job_id)
            if not job:
                raise exc.NotFoundError(
                    'job does not exist: {}'.format(job_id)
                )
            return job

        @webutils.post_api(api, cors,
                           req_model=req_model,
                           resp_model=resp_model)
        def post(self, job_id):
            """Creates Treadmill cron."""
            return impl.create(job_id, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=req_model,
                          resp_model=resp_model,
                          parser=resume_pause_parser)
        def put(self, job_id):
            """Updates Treadmill cron configuration."""
            args = resume_pause_parser.parse_args()
            return impl.update(job_id, flask.request.json, **args)

        @webutils.delete_api(api, cors)
        def delete(self, job_id):
            """Deletes Treadmill cron."""
            return impl.delete(job_id)
