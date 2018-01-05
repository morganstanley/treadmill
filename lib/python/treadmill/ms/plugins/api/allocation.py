"""Allocation plugin.

Adds rank adjustment attribute to reservations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import admin
from treadmill import context
from treadmill import exc

_LOGGER = logging.getLogger(__name__)

_RANK_ADJUSTMENTS = {
    'dev': 0,
    'qa': 10,
    'uat': 20,
    'prod': 30,
}


def remove_attributes(manifest):
    """Remove dynamically added attributes."""
    return manifest


def add_attributes(rsrc_id, manifest):
    """Add rank adjustment to reservation."""
    allocation, _cell = rsrc_id.rsplit('/', 1)
    alloc = admin.Allocation(context.GLOBAL.ldap.conn)

    alloc_obj = alloc.get(allocation)

    env = alloc_obj['environment']
    if env not in _RANK_ADJUSTMENTS.keys():
        raise exc.InvalidInputError(
            __name__, 'Invalid environment: %s' % env)

    updated = {
        'rank_adjustment': _RANK_ADJUSTMENTS[env]
    }

    _LOGGER.info('Adding attributes: %r', updated)

    updated.update(manifest)
    return updated
