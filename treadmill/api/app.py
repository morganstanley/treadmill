"""Implementation of app API."""


import logging

import jsonschema.exceptions

from .. import context
from .. import schema
from .. import authz
from .. import admin

from treadmill.appmgr import features


_LOGGER = logging.getLogger(__name__)


def verify_feature(app_features):
    """Verify that any feature in this resource has a corresponding module"""
    for feature in app_features:
        if feature not in features.ALL_FEATURES:
            raise jsonschema.exceptions.ValidationError(
                'Unsupported feature: ' + feature
            )


class API(object):
    """Treadmill App REST api."""

    def __init__(self):

        def _admin_app():
            """Lazily return admin object."""
            return admin.Application(context.GLOBAL.ldap.conn)

        def _list():
            """List configured applications."""
            return _admin_app().list({})

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
            return _admin_app().get(rsrc_id)

        @schema.schema(
            {'$ref': 'app.json#/resource_id'},
            {'allOf': [{'$ref': 'app.json#/resource'},
                       {'$ref': 'app.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            verify_feature(rsrc.get('features', []))

            _admin_app().replace(rsrc_id, rsrc)
            return _admin_app().get(rsrc_id)

        @schema.schema({'$ref': 'app.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app().delete(rsrc_id)
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
