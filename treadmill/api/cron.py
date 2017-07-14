"""Implementation of cron API.
"""

import fnmatch
import logging

from treadmill import authz
from treadmill import context
from treadmill import cron
from treadmill import schema
from treadmill.cron import model as cron_model

_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill Cron REST api."""

    def __init__(self):
        self.scheduler = None

        def _list(match=None):
            pass

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def get(rsrc_id):
            pass

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/resource'},
                       {'$ref': 'cron.json#/verbs/create'}]},
        )
        def create(rsrc_id, rsrc):
            pass

        @schema.schema(
            {'$ref': 'cron.json#/resource_id'},
            {'allOf': [{'$ref': 'cron.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            pass

        @schema.schema({'$ref': 'cron.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured instance."""
            pass

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
