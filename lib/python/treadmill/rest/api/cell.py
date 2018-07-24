"""Treadmill Cell REST api.
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
    """Configures REST handlers for cell resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cell REST operations'
    )

    master = api.model('Master', {
        'hostname': fields.String(description='Hostname'),
        'idx': fields.Integer(description='Index of master'),
        'zk-followers-port': fields.Integer(description='ZK follower port'),
        'zk-election-port': fields.Integer(description='ZK election port'),
        'zk-jmx-port': fields.Integer(description='ZK JMX port'),
        'zk-client-port': fields.Integer(description='ZK client port'),
    })
    partition = api.model('Partition', {
        'partition': fields.String(description='Name'),
        'cpu': fields.String(description='Total cpu capacity'),
        'disk': fields.String(description='Total disk capacity'),
        'memory': fields.String(description='Total memory capacity'),
        'systems': fields.List(fields.Integer(description='System')),
        'down-threshold': fields.String(description='Server down threshold'),
        'reboot-schedule': fields.String(description='Reboot schedule'),
    })
    model = {
        '_id': fields.String(description='Name'),
        'username': fields.String(description='Treadmill User ID'),
        'zk-auth-scheme': fields.String(description='Zookeeper auth scheme'),
        'root': fields.String(description='Treadmill Root'),
        'location': fields.String(description='Location'),
        'version': fields.String(description='Version'),
        'status': fields.String(description='Status'),
        'masters': fields.List(fields.Nested(master)),
        'partitions': fields.List(fields.Nested(partition)),
        'data': fields.Raw(),
    }

    cell_model = api.model(
        'Cell', model
    )

    @namespace.route('/')
    class _CellList(restplus.Resource):
        """Treadmill Cell resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=cell_model)
        def get(self):
            """Returns list of configured cells."""
            return impl.list()

    @namespace.route('/<cell>')
    @api.doc(params={'cell': 'Cell ID/name'})
    class _CellResource(restplus.Resource):
        """Treadmill Cell resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=cell_model)
        def get(self, cell):
            """Return Treadmill cell configuration."""
            return impl.get(cell)

        @webutils.post_api(api, cors,
                           req_model=cell_model,
                           resp_model=cell_model)
        def post(self, cell):
            """Creates Treadmill cell."""
            return impl.create(cell, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=cell_model,
                          resp_model=cell_model)
        def put(self, cell):
            """Updates Treadmill cell configuration."""
            return impl.update(cell, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, cell):
            """Deletes Treadmill cell."""
            return impl.delete(cell)
