"""Implementation of Allocation-group API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import schema

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import allocation_group

_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill Allocation-group REST api."""

    def __init__(self):
        """init"""

        @schema.schema({'$ref': 'allocation_group.json#/resource_id'})
        def get(rsrc_id):
            """Get allocation-group."""
            return allocation_group.get(rsrc_id)

        @schema.schema(
            {'$ref': 'allocation_group.json#/resource_id'},
            {'allOf': [{'$ref': 'allocation_group.json#/resource'},
                       {'$ref': 'allocation_group.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create allocation-group."""
            allocation_group.create(
                rsrc_id,
                rsrc['eonid'],
                rsrc['environment']
            )

            if 'admins' in rsrc and rsrc['admins']:
                allocation_group.insert(rsrc_id, rsrc['admins'])

            return None

        @schema.schema(
            {'$ref': 'allocation_group.json#/resource_id'},
            {'allOf': [{'$ref': 'allocation_group.json#/resource'},
                       {'$ref': 'allocation_group.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update allocation-group."""
            old = allocation_group.get(rsrc_id)
            to_remove = list(set(old['admins']) - set(rsrc['admins']))

            if rsrc['admins']:
                allocation_group.insert(rsrc_id, rsrc['admins'])
            if to_remove:
                allocation_group.remove(rsrc_id, to_remove)

            return None

        @schema.schema({'$ref': 'allocation_group.json#/resource_id'})
        def delete(rsrc_id):
            """Delete allocation-group."""
            allocation_group.delete(rsrc_id)

            return None

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
