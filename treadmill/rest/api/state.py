"""
Treadmill State REST api.
"""


import http.client

import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for state resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'State REST operations'
    )

    state_model = {
        'name': fields.String(description='Application name'),
        'host': fields.String(description='Application host'),
        'state': fields.String(description='Application state'),
        'expires': fields.Float(description='Host expiration'),
    }

    response_model = api.model(
        'RespState', state_model
    )

    match_parser = api.parser()
    match_parser.add_argument('match', help='A glob match on an app name',
                              location='args', required=False,)

    inst_parser = api.parser()
    inst_parser.add_argument('instances', type=dict,
                             location='json', required=True,
                             help='List of instances, e.g.: '
                             '{ "instances": ["proid.app#0000000000"]}')

    @namespace.route(
        '/',
    )
    class _StateList(restplus.Resource):
        """Treadmill State resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model,
                          parser=match_parser)
        def get(self):
            """Return all state."""
            args = match_parser.parse_args()
            return impl.list(args.get('match'))

        @webutils.post_api(api, cors,
                           marshal=api.marshal_list_with,
                           resp_model=response_model,
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
                          resp_model=response_model)
        def get(self, instance_id):
            """Return Treadmill instance state."""
            state = impl.get(instance_id)
            if state is None:
                api.abort(http.client.NOT_FOUND,
                          'Instance does not exist: %s' % instance_id)
            return state
