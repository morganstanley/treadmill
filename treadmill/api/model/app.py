"""
Application API data models
"""

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
    })
    endpoint = api.model('Endpoint', {
        'name': fields.String(description='Endpoint Name', required=True),
        'port': fields.Integer(description='Port', required=True),
        'type': fields.String(description='Type'),
        'proto': fields.String(description='Protocol'),
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
        'cells': fields.List(fields.String(description='Cell')),
        'rules': fields.List(fields.Nested(vring_rule)),
    })

    application = {
        '_id': fields.String(description='Name'),
        'memory': fields.String(description='Memory'),
        'cpu': fields.String(description='CPU'),
        'disk': fields.String(description='Disk size'),
        'services': fields.List(fields.Nested(service)),
        'environ': fields.List(fields.Nested(environ)),
        'endpoints': fields.List(fields.Nested(endpoint)),
        'ephemeral_ports': fields.Integer(description='Epemeral Ports'),
        'tickets': fields.List(fields.String(description='Tickets')),
        'features': fields.List(fields.String(description='Features')),
        'identity_group': fields.String(description='Identity Group'),
        'archive': fields.List(fields.String(description='Archive')),
        'shared_ip': fields.Boolean(description='Shared IP'),
        'shared_network': fields.Boolean(description='Shared Network'),
        'schedule_once': fields.Boolean(description='Schedule Once'),
        'vring': fields.Nested(vring),
    }

    request_model = api.model(
        'Application', application
    )
    response_model = api.model(
        'Application', application
    )

    return (request_model, response_model)
