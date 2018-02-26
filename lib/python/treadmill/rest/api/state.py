"""Treadmill State REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_restplus as restplus
from flask_restplus import fields, inputs

from treadmill import exc
from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for state resource."""
    namespace = webutils.namespace(
        api, __name__, 'State REST operations'
    )

    model = {
        'name': fields.String(description='Application name'),
        'host': fields.String(description='Application host'),
        'state': fields.String(description='Application state'),
        'expires': fields.Float(description='Host expiration'),
        'when': fields.Float(description='Timestamp of event'),
        'signal': fields.Integer(description='Kill signal'),
        'exitcode': fields.Integer(description='Service exitcode'),
        'aborted_reason': fields.String(description='Aborted reason'),
        'oom': fields.Boolean(description='Out of memory'),
    }

    state_model = api.model(
        'State', model
    )

    query_param_parser = api.parser()
    query_param_parser.add_argument(
        'match', help='A glob match on an app name',
        location='args', required=False
    )
    query_param_parser.add_argument(
        'finished', help='Flag to include finished apps',
        location='args', required=False,
        type=inputs.boolean, default=False
    )
    query_param_parser.add_argument(
        'partition', help='Filter apps by partition',
        location='args', required=False
    )

    inst_parser = api.parser()
    inst_parser.add_argument('instances', type=list,
                             location='json', required=True,
                             help='List of instances, e.g.: '
                             '{ "instances": ["proid.app#0000000000"]}')

    @namespace.route(
        '/',
    )
    class _StateList(restplus.Resource):
        """Treadmill State resource"""

        @webutils.get_api(
            api, cors,
            marshal=api.marshal_list_with,
            resp_model=state_model,
            parser=query_param_parser
        )
        def get(self):
            """Return all state."""
            args = query_param_parser.parse_args()
            return impl.list(
                args.get('match'),
                args.get('finished'),
                args.get('partition')
            )

        @webutils.post_api(api, cors,
                           marshal=api.marshal_list_with,
                           resp_model=state_model,
                           parser=inst_parser)
        def post(self):
            """Returns state of the instance list."""
            args = inst_parser.parse_args()
            instances = args.get('instances')
            states = [impl.get(instance_id) for instance_id in instances]
            return [state for state in states if state is not None]

    @namespace.route('/<instance_id>')
    @api.doc(params={'instance_id': 'Application instance ID'})
    class _StateResource(restplus.Resource):
        """Treadmill State resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=state_model)
        def get(self, instance_id):
            """Return Treadmill instance state."""
            state = impl.get(instance_id)
            if state is None:
                raise exc.NotFoundError(
                    'Instance does not exist: {}'.format(instance_id)
                )
            return state
