"""Implementation of AppGroup API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch

from treadmill import context
from treadmill import schema


class API:
    """Treadmill AppGroup REST api."""

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin object."""
            return context.GLOBAL.admin.app_group()

        @schema.schema({'$ref': 'app_group.json#/resource_id'})
        def get(rsrc_id):
            """Get application configuration."""
            result = _admin_app_group().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        @schema.schema(
            {'$ref': 'app_group.json#/resource_id'},
            {'allOf': [{'$ref': 'app_group.json#/resource'},
                       {'$ref': 'app_group.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application."""
            _admin_app_group().create(rsrc_id, rsrc)
            return _admin_app_group().get(rsrc_id, dirty=True)

        @schema.schema(
            {'$ref': 'app_group.json#/resource_id'},
            {'allOf': [{'$ref': 'app_group.json#/resource'},
                       {'$ref': 'app_group.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            _admin_app_group().replace(rsrc_id, rsrc)
            return _admin_app_group().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'app_group.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app_group().delete(rsrc_id)

        def _list(match=None):
            """List configured applications."""
            if match is None:
                match = '*'

            app_groups = _admin_app_group().list({})
            filtered = [
                app_group for app_group in app_groups
                if fnmatch.fnmatch(app_group['_id'], match)
            ]
            return sorted(filtered, key=lambda item: item['_id'])

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.list = _list
