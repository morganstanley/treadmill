"""Implementation of DNS server API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import context
from treadmill import schema


class API:
    """Treadmill DNS REST api."""

    def __init__(self):

        def _admin_dns():
            """Lazily return DNS admin object"""
            return context.GLOBAL.admin.dns()

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
