"""Implementation of API lookup API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import context
from treadmill import dnsutils
from treadmill import schema


class NoSuchCellException(Exception):
    """No such cell exception class"""

    def __init__(self, cell):
        self.message = 'No such cell: {}'.format(cell)
        self.cell = cell
        super(NoSuchCellException, self).__init__(self.message)

    def __str__(self):
        return 'No such cell: {}'.format(self.cell)


def _set_auth_resource(cls, resource):
    """Set auth resource name for CRUD methods of the class."""
    for method_name in ['get', 'create', 'update', 'delete']:
        method = getattr(cls, method_name, None)
        if method:
            method.auth_resource = resource


def _result_to_resource(result):
    """Turn SRV result into resource."""
    targets = [dnsutils.srv_target_to_dict(tgt)
               for tgt in result]
    return {'targets': targets}


class API:
    """Treadmill API lookup API."""

    def __init__(self):
        ctx = context.GLOBAL

        def _list():
            """No LIST method.
            """

        def _get():
            """No GET method.
            """

        class _AdminApiLookupAPI:
            """Treadmill Admin API Lookup API"""

            def __init__(self):

                def _list():
                    """No LIST method.
                    """

                @schema.schema()
                def get():
                    """Get Admin API SRV records"""
                    result = ctx.dns.admin_api_srv()
                    return _result_to_resource(result)

                self.list = _list
                self.get = get

                _set_auth_resource(self, 'adminapi')

        class _CellApiLookupAPI:
            """Treadmill Cell API Lookup API"""

            def __init__(self):
                @schema.schema({'$ref': 'api_lookup.json#/cell_name'})
                def get(cell_name):
                    """Get Cell API SRV records for given cell"""
                    try:
                        result = ctx.dns.cell_api_srv(cell_name)
                        return _result_to_resource(result)
                    except context.ContextError:
                        raise NoSuchCellException(cell_name)

                def _list():
                    return []

                self.get = get
                self.list = _list

                _set_auth_resource(self, 'cellapi')

        class _StateApiLookupAPI:
            """Treadmill State API Lookup API"""

            def __init__(self):

                @schema.schema({'$ref': 'api_lookup.json#/cell_name'})
                def get(cell_name):
                    """Get State API SRV records for given cell"""
                    try:
                        result = ctx.dns.state_api_srv(cell_name)
                        return _result_to_resource(result)
                    except context.ContextError:
                        raise NoSuchCellException(cell_name)

                def _list():
                    return []

                self.get = get
                self.list = _list

                _set_auth_resource(self, 'statepi')

        class _WsApiLookupAPI:
            """Treadmill WS API Lookup API"""

            def __init__(self):
                @schema.schema({'$ref': 'api_lookup.json#/cell_name'})
                def get(cell_name):
                    """Get WS API SRV records for given cell"""
                    try:
                        result = ctx.dns.ws_api_srv(cell_name)
                        return _result_to_resource(result)
                    except context.ContextError:
                        raise NoSuchCellException(cell_name)

                def _list():
                    return []

                self.get = get
                self.list = _list

                _set_auth_resource(self, 'wsapi')

        self.list = _list
        self.get = _get
        self.adminapi = _AdminApiLookupAPI()
        self.cellapi = _CellApiLookupAPI()
        self.stateapi = _StateApiLookupAPI()
        self.wsapi = _WsApiLookupAPI()
