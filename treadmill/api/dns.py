"""Implementation of DNS server API."""


from treadmill import admin
from treadmill import authz
from treadmill import context
from treadmill import schema


class API(object):
    """Treadmill DNS REST api."""

    def __init__(self):

        def _admin_dns():
            """Lazily return DNS admin object"""
            return admin.DNS(context.GLOBAL.ldap.conn)

        def _list():
            """List DNS servers"""
            return _admin_dns().list({})

        @schema.schema({'$ref': 'dns.json#/resource_id'})
        def get(rsrc_id):
            """Get DNS server entry"""
            result = _admin_dns().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        self.list = _list
        self.get = get


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
