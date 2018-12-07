"""Implementation of app API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import fnmatch
import re

import jsonschema.exceptions

from treadmill import context
from treadmill import schema

from treadmill.appcfg import features


_LOGGER = logging.getLogger(__name__)


def verify_feature(app_features):
    """Verify that any feature in this resource has a corresponding module"""
    for feature in app_features:
        if not features.feature_exists(feature):
            raise jsonschema.exceptions.ValidationError(
                'Unsupported feature: ' + feature
            )


class API:
    """Treadmill App REST api."""

    def __init__(self):

        def _admin_app():
            """Lazily return admin object."""
            return context.GLOBAL.admin.application()

        def _list(match=None):
            """List configured applications."""
            if match is None:
                match = '*'

            # If match contains full proid, do initial server-side filtering.
            attrs = {}
            res = re.search(r'^([\w-]+)\.', match)
            if res:
                proid = res.group(1)
                attrs = {'_id': '{0}.*'.format(proid)}

            apps = _admin_app().list(attrs, generator=True)
            filtered = [
                app for app in apps
                if fnmatch.fnmatch(app['_id'], match)
            ]
            return sorted(filtered, key=lambda item: item['_id'])

        @schema.schema({'$ref': 'app.json#/resource_id'})
        def get(rsrc_id):
            """Get application configuration."""
            result = _admin_app().get(rsrc_id)
            result['_id'] = rsrc_id
            return result

        @schema.schema(
            {'$ref': 'app.json#/resource_id'},
            {'allOf': [{'$ref': 'app.json#/resource'},
                       {'$ref': 'app.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application."""
            verify_feature(rsrc.get('features', []))

            _admin_app().create(rsrc_id, rsrc)
            return _admin_app().get(rsrc_id, dirty=True)

        @schema.schema(
            {'$ref': 'app.json#/resource_id'},
            {'allOf': [{'$ref': 'app.json#/resource'},
                       {'$ref': 'app.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            verify_feature(rsrc.get('features', []))

            _admin_app().replace(rsrc_id, rsrc)
            return _admin_app().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'app.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app().delete(rsrc_id)

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
