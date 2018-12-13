"""
Application API data models
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from flask_restplus import fields


def models(api):
    """Get the request and response models"""
    restart = api.model('Restart', {
        'limit': fields.Integer(description='Limit', required=True),
        'interval': fields.Integer(description='Interval'),
    })
    service = api.model('Service', {
        'name': fields.String(description='Name', required=True),
        'command': fields.String(description='Command'),
        'restart': fields.Nested(restart),
        'root': fields.Boolean(description='Run as root'),
        'image': fields.String(description='Docker image'),
        'useshell': fields.Boolean(
            description='Use a shell to interpret the Treadmill command'
        ),
    })
    endpoint = api.model('AppEndpoint', {
        'name': fields.String(description='Endpoint Name', required=True),
        'port': fields.Integer(description='Port', required=True),
        'type': fields.String(description='Type'),
        'proto': fields.String(description='Protocol'),
    })
    ephemeral_ports = api.model('Ephemeral', {
        'tcp': fields.Integer(description='TCP port count', required=False),
        'udp': fields.Integer(description='UDP port count', required=False),
    })
    environ = api.model('EnvironmentVars', {
        'name': fields.String(description='Name'),
        'value': fields.String(description='Value'),
    })
    vring_rule = api.model('VRingRule', {
        'endpoints': fields.List(fields.String(description='Endpoint names')),
        'pattern': fields.String(description='Pattern'),
    })
    vring = api.model('VRing', {
        'cells': fields.List(fields.String(description='Cell')),
        'rules': fields.List(fields.Nested(vring_rule)),
    })
    affinity_limits = api.model('AffinityLimit', {
        'pod': fields.Integer(description='Pod'),
        'rack': fields.Integer(description='Rack'),
        'server': fields.Integer(description='Server'),
    })

    application = {
        '_id': fields.String(description='Name'),
        'memory': fields.String(description='Memory'),
        'cpu': fields.String(description='CPU'),
        'disk': fields.String(description='Disk size'),
        'services': fields.List(fields.Nested(service)),
        'image': fields.String(description='Image'),
        'command': fields.String(description='Command'),
        'args': fields.List(fields.String(description='Arguments')),
        'environ': fields.List(fields.Nested(environ)),
        'endpoints': fields.List(fields.Nested(endpoint)),
        'ephemeral_ports': fields.Nested(ephemeral_ports),
        'tickets': fields.List(fields.String(description='Tickets')),
        'features': fields.List(fields.String(description='Features')),
        'passthrough': fields.List(fields.String(description='Passthrough')),
        'identity_group': fields.String(description='Identity Group'),
        'archive': fields.List(fields.String(description='Archive')),
        'shared_ip': fields.Boolean(description='Shared IP'),
        'shared_network': fields.Boolean(description='Shared Network'),
        'schedule_once': fields.Boolean(description='Schedule Once'),
        'vring': fields.Nested(vring),
        'data_retention_timeout': fields.String(
            description='Data retention timeout'),
        'lease': fields.String(description='Application lease interval.'),
        'affinity_limits': fields.Nested(affinity_limits),
        'traits': fields.List(fields.String(description='Traits')),
    }

    app_model = api.model(
        'Application', application
    )

    return (app_model, app_model)
