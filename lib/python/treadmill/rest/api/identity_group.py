"""Treadmill Identity Group REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for app monitor resource."""

    namespace = webutils.namespace(
        api, __name__, 'Identity Group REST operations'
    )

    model = {
        '_id': fields.String(description='Name'),
        'count': fields.Integer(
            description='Identiy Group Count',
            required=True),
    }

    identity_group_model = api.model(
        'IdentityGroup', model
    )

    match_parser = api.parser()
    match_parser.add_argument('match', help='A glob match on an app monitor',
                              location='args', required=False,)

    @namespace.route(
        '/',
    )
    class _IdentityGroupList(restplus.Resource):
        """Treadmill identity group resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=identity_group_model,
                          parser=match_parser)
        def get(self):
            """Returns list of configured identity groups."""
            args = match_parser.parse_args()
            return impl.list(args.get('match'))

    @namespace.route('/<app_id>')
    @api.doc(params={'app_ip': 'App ID/name'})
    class _IdentityGroupResource(restplus.Resource):
        """Treadmill identity group resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=identity_group_model)
        def get(self, app_id):
            """Return identity group configuration."""
            return impl.get(app_id)

        @webutils.post_api(api, cors,
                           req_model=identity_group_model,
                           resp_model=identity_group_model)
        def post(self, app_id):
            """Creates identity group."""
            return impl.create(app_id, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=identity_group_model,
                          resp_model=identity_group_model)
        def put(self, app_id):
            """Updates identity group configuration."""
            return impl.update(app_id, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_id):
            """Deletes identity group."""
            return impl.delete(app_id)
