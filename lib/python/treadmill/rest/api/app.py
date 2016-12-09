"""
Treadmill App REST api.
"""
from __future__ import absolute_import

import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for app resource."""

    namespace = webutils.namespace(
        api, __name__, 'Application REST operations'
    )

    restart = api.model('Restart', {
        'limit': fields.Integer(
            description='Limit',
            min=0, max=10, required=True),
        'interval': fields.Integer(
            description='Interval',
            min=30, max=600),
    })
    service = api.model('Service', {
        'name': fields.String(
            description='Name',
            max_length=60, pattern=r'/^[\w\-\.]+$/', required=True),
        'command': fields.String(description='Command'),
        'restart': fields.Nested(restart),
    })
    endpoint = api.model('Endpoint', {
        'name': fields.String(
            description='Endpoint Name',
            max_length=20, pattern=r'/^[\w\-]+$/', required=True),
        'port': fields.Integer(
            description='Port',
            min=0, max=65535, required=True),
        'type': fields.String(description='Type', pattern=r'/^infra$/'),
        'proto': fields.String(description='Protocol', pattern=r'/^tcp|udp$/'),
    })
    environ = api.model('EnvironmentVars', {
        'name': fields.String(description='Name'),
        'value': fields.String(description='Value'),
    })
    vring_rule = api.model('VRingRule', {
        'endpoints': fields.List(fields.Nested(endpoint)),
        'pattern': fields.String(description='Pattern'),
    })
    vring = api.model('VRing', {
        'cells': fields.List(fields.String(
            description='Cell',
            max_length=20, pattern=r'/^[a-zA-Z0-9-]+$/')),
        'rules': fields.List(fields.Nested(vring_rule)),
    })

    application = {
        '_id': fields.String(
            description='Name',
            max_length=60,
            pattern=(
                r'/^([\w\-]+(\.[\w\-]+)+)|'
                r'(([\w\-]+)@([\w\-]+)(\.[\w\-]+)+)$/')),
        'memory': fields.String(
            description='Memory',
            pattern=r'/\d+[KkMmGg]$/'),
        'cpu': fields.String(description='CPU', pattern=r'/\d+%/'),
        'disk': fields.String(
            description='Disk size',
            pattern=r'/\d+[KkMmGg]$/'),
        'services': fields.List(fields.Nested(service)),
        'environ': fields.List(fields.Nested(environ)),
        'endpoints': fields.List(fields.Nested(endpoint)),
        'ephemeral_ports': fields.Integer(
            description='Epemeral Ports',
            min=0, max=250),
        'ticket': fields.List(fields.String(
            description='Tickets', max_length=32,
            pattern=r'/^[a-zA-Z0-9_]+@[\.a-zA-Z0-9_]+$/')),
        'features': fields.List(fields.String(
            description='Features',
            pattern=r'/^[\w\-]+$/')),
        'identity_group': fields.String(
            description='Identity Group', max_length=128,
            pattern=r'/^[\w\-]+(\.[\w\-]+)+$/'),
        'archive': fields.List(fields.String(description='Archive')),
        'shared_ip': fields.Boolean(description='Shared IP'),
        'shared_network': fields.Boolean(description='Shared Network'),
        'schedule_once': fields.Boolean(description='Schedule Once'),
        'vring': fields.Nested(vring),
    }

    request_model = namespace.model(
        'ReqApplication', application
    )
    response_model = namespace.model(
        'RespApplication', application
    )

    @namespace.route(
        '/',
    )
    class _AppList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Returns list of configured applications."""
            ret = impl.list()
            print 'ret: ', ret
            return ret

    @namespace.route('/<app>')
    @api.doc(params={'app': 'Application ID/Name'})
    class _AppResource(restplus.Resource):
        """Treadmill App resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, app):
            """Return Treadmill application configuration."""
            return impl.get(app)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, app):
            """Creates Treadmill application."""
            return impl.create(app, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, app):
            """Updates Treadmill application configuration."""
            return impl.update(app, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, app):
            """Deletes Treadmill application."""
            return impl.delete(app)
