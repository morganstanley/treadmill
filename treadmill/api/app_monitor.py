"""Implementation of app API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import fnmatch

from treadmill import context
from treadmill import schema
from treadmill import authz
from treadmill import master


_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill AppMonitor REST api."""

    def __init__(self):

        def _list(match=None):
            """List configured monitors."""
            if match is None:
                match = '*'

            zkclient = context.GLOBAL.zk.conn
            monitors = [
                master.get_appmonitor(zkclient, app)
                for app in master.appmonitors(zkclient)
            ]

            filtered = [
                monitor for monitor in monitors
                if (monitor is not None and
                    fnmatch.fnmatch(monitor['_id'], match))
            ]
            return sorted(filtered)

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
        )
        def get(rsrc_id):
            """Get application monitor configuration."""
            zkclient = context.GLOBAL.zk.conn
            return master.get_appmonitor(zkclient, rsrc_id,
                                         raise_notfound=True)

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
            {'allOf': [{'$ref': 'appmonitor.json#/resource'},
                       {'$ref': 'appmonitor.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application monitor."""
            zkclient = context.GLOBAL.zk.conn
            master.update_appmonitor(zkclient, rsrc_id, rsrc['count'])
            return master.get_appmonitor(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
            {'allOf': [{'$ref': 'appmonitor.json#/resource'},
                       {'$ref': 'appmonitor.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            zkclient = context.GLOBAL.zk.conn
            master.update_appmonitor(zkclient, rsrc_id, rsrc['count'])
            return master.get_appmonitor(zkclient, rsrc_id)

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
        )
        def delete(rsrc_id):
            """Delete configured application monitor."""
            zkclient = context.GLOBAL.zk.conn
            master.delete_appmonitor(zkclient, rsrc_id)
            return None

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
