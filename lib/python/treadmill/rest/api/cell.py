"""
Treadmill Cell REST api.
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
    """Configures REST handlers for cell resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cell REST operations'
    )

    cell_model = {
        '_id': fields.String(
            description='Name',
            max_length=20,
            pattern=r'/^[a-zA-Z0-9-]+$/'),
        'treadmillid': fields.String(
            description='Treadmill User ID',
            max_length=16,
            pattern=r'/^[a-zA-Z0-9_]+$/'),
        'treadmill_root': fields.String(description='Treadmill Root'),
        'archive_server': fields.String(description='Archive Server'),
        'archive_username': fields.String(description='Archive Username'),
        'ssq_namespace': fields.String(description='SSQ Namespace'),
        'location': fields.String(
            description='Location',
            pattern=r'/^[a-zA-Z]+$/'),
        'version': fields.String(description='Version'),
    }

    request_model = api.model(
        'ReqCell', cell_model
    )
    response_model = api.model(
        'RespCell', cell_model
    )

    @namespace.route('/')
    class _CellList(restplus.Resource):
        """Treadmill Cell resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=response_model)
        def get(self):
            """Returns list of configured cells."""
            return impl.list()

    @namespace.route('/<cell>')
    @api.doc(params={'cell': 'Cell ID/name'})
    class _CellResource(restplus.Resource):
        """Treadmill Cell resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=response_model)
        def get(self, cell):
            """Return Treadmill cell configuration."""
            return impl.get(cell)

        @webutils.post_api(api, cors,
                           req_model=request_model,
                           resp_model=response_model)
        def post(self, cell):
            """Creates Treadmill cell."""
            return impl.create(cell, flask.request.json)

        @webutils.put_api(api, cors,
                          req_model=request_model,
                          resp_model=response_model)
        def put(self, cell):
            """Updates Treadmill cell configuration."""
            return impl.update(cell, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, cell):
            """Deletes Treadmill cell."""
            return impl.delete(cell)
