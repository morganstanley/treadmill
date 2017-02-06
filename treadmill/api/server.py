"""Implementation of server API."""


from .. import admin
from .. import authz
from .. import context
from .. import schema


class API(object):
    """Treadmill Server REST api."""

    def __init__(self):

        def _admin_svr():
            """Lazily return admin object."""
            return admin.Server(context.GLOBAL.ldap.conn)

        @schema.schema(
            cell={'anyOf': [{'type': 'null'}, {'$ref': 'common.json#/cell'}]},
            label={'anyOf': [
                {'type': 'null'},
                {'$ref': 'server.json#/resource/properties/label'}
            ]}
        )
        # () will not pass validation, but it is indication for introspection
        # that the required type is list.
        def _list(cell=None, label=()):
            """List servers by cell and/or features."""
            if label == ():
                label = None

            filter_ = {}
            if cell:
                filter_['cell'] = cell

            if label:
                filter_['label'] = label

            return _admin_svr().list(filter_)

        @schema.schema({'$ref': 'server.json#/resource_id'})
        def get(rsrc_id):
            """Get server configuration."""
            result = _admin_svr().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        @schema.schema({'$ref': 'server.json#/resource_id'},
                       {'allOf': [{'$ref': 'server.json#/resource'},
                                  {'$ref': 'server.json#/verbs/create'}]})
        def create(rsrc_id, rsrc):
            """Create server."""
            _admin_svr().create(rsrc_id, rsrc)
            return _admin_svr().get(rsrc_id)

        @schema.schema({'$ref': 'server.json#/resource_id'},
                       {'allOf': [{'$ref': 'server.json#/resource'},
                                  {'$ref': 'server.json#/verbs/update'}]})
        def update(rsrc_id, rsrc):
            """Update server."""
            _admin_svr().update(rsrc_id, rsrc)
            return _admin_svr().get(rsrc_id)

        @schema.schema({'$ref': 'server.json#/resource_id'})
        def delete(rsrc_id):
            """Delete server."""
            _admin_svr().delete(rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
