"""Treadmill App Event REST API.
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
    """Configures REST handlers for app-event resource."""

    namespace = webutils.namespace(
        api, __name__, 'App Event REST operations'
    )

    model = {
        '_id': fields.String(description='Name'),
        'cells': fields.List(fields.String(description='Cells')),
        'pattern': fields.String(description='App pattern'),
        'pending': fields.Integer(description='pending'),
        'exit': fields.List(fields.String(
            enum=['non-zero', 'aborted', 'oom'],
            description='exit'
        )),
    }

    app_event_model = api.model(
        'AppEvent', model
    )

    @namespace.route(
        '/',
    )
    class _AppEventList(restplus.Resource):
        """Treadmill app-event resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=app_event_model)
        def get(self):
            """Returns list of configured app-event."""
            return impl.list()

    @namespace.route('/<app_event>')
    @api.doc(params={'app_event': 'Application Event ID/name'})
    class _AppEventResource(restplus.Resource):
        """Treadmill App Event resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=app_event_model)
        def get(self, app_event):
            """Return Treadmill app-event configuration."""
            return impl.get(app_event)

        @webutils.post_api(api, cors,
                           req_model=app_event_model,
                           resp_model=app_event_model)
        def post(self, app_event):
            """Creates Treadmill app-event."""
            return impl.create(app_event, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=app_event_model,
                          resp_model=app_event_model)
        def put(self, app_event):
            """Updates Treadmill app-event configuration."""
            return impl.update(app_event, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app_event):
            """Deletes Treadmill app-event."""
            return impl.delete(app_event)
