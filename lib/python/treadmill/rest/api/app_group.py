"""Treadmill AppGroup REST api.
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
    """Configures REST handlers for app_group resource."""

    namespace = webutils.namespace(
        api, __name__, 'AppGroup REST operations'
    )

    model = {
        '_id': fields.String(description='Name'),
        'cells': fields.List(fields.String(description='Cells')),
        'group-type': fields.String(description='Group Type'),
        'pattern': fields.String(description='Pattern'),
        'data': fields.String(description='Data'),
    }

    app_group_model = api.model(
        'AppGroup', model
    )

    match_parser = api.parser()
    match_parser.add_argument('match', help='A glob match on an app group',
                              location='args', required=False,)

    @namespace.route(
        '/',
    )
    class _AppGroupList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=app_group_model,
                          parser=match_parser)
        def get(self):
            """Returns list of configured applications."""
            args = match_parser.parse_args()
            return impl.list(args.get('match'))

    @namespace.route('/<app_group>')
    @api.doc(params={'app_group': 'App Group ID/name'})
    class _AppGroupResource(restplus.Resource):
        """Treadmill AppGroup resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=app_group_model)
        def get(self, app_group):
            """Return Treadmill app-group configuration."""
            return impl.get(app_group)

        @webutils.post_api(api, cors,
                           req_model=app_group_model,
                           resp_model=app_group_model)
        def post(self, app_group):
            """Creates Treadmill app-group."""
            return impl.create(app_group, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=app_group_model,
                          resp_model=app_group_model)
        def put(self, app_group):
            """Updates Treadmill app-group configuration."""
            return impl.update(app_group, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_group):
            """Deletes Treadmill app-group."""
            return impl.delete(app_group)
