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
from treadmill.scheduler import masterapi


_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill AppMonitor REST api."""

    def __init__(self):

        def _list(match=None):
            """List configured monitors."""
            if match is None:
                match = '*'

            zkclient = context.GLOBAL.zk.conn

            # get suspended monitors
            suspended_monitors = masterapi.get_suspended_appmonitors(zkclient)

            monitors = [
                masterapi.get_appmonitor(
                    zkclient, app,
                    suspended_monitors=suspended_monitors,
                )
                for app in masterapi.appmonitors(zkclient)
            ]

            filtered = [
                monitor for monitor in monitors
                if (monitor is not None and
                    fnmatch.fnmatch(monitor['_id'], match))
            ]
            return sorted(filtered, key=lambda item: item['_id'])

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
        )
        def get(rsrc_id):
            """Get application monitor configuration."""
            zkclient = context.GLOBAL.zk.conn
            return masterapi.get_appmonitor(zkclient, rsrc_id,
                                            raise_notfound=True)

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
            {'allOf': [{'$ref': 'appmonitor.json#/resource'},
                       {'$ref': 'appmonitor.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application monitor."""
            zkclient = context.GLOBAL.zk.conn
            return masterapi.update_appmonitor(
                zkclient, rsrc_id, rsrc['count'], rsrc.get('policy'),
            )

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
            {'allOf': [{'$ref': 'appmonitor.json#/resource'},
                       {'$ref': 'appmonitor.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            zkclient = context.GLOBAL.zk.conn
            return masterapi.update_appmonitor(
                zkclient, rsrc_id, rsrc.get('count'), rsrc.get('policy'),
            )

        @schema.schema(
            {'$ref': 'appmonitor.json#/resource_id'},
        )
        def delete(rsrc_id):
            """Delete configured application monitor."""
            zkclient = context.GLOBAL.zk.conn
            masterapi.delete_appmonitor(zkclient, rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
