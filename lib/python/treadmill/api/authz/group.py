"""Implementation of group based authorization API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import grp
import logging

_LOGGER = logging.getLogger(__name__)


def _group(template, resource, action, proid):
    """Render group template."""
    return template.format(
        resource=resource,
        action=action,
        proid=proid
    )


class API:
    """Group based authorization REST api."""

    def __init__(self, **kwargs):

        groups = kwargs.get('groups', [])
        for group in groups:
            _LOGGER.info('Using authorization template: %s', group)

        # TODO: add schema validation.
        def authorize(user, action, resource, resource_id, payload):
            """Authorize user/action/resource"""
            del payload
            _LOGGER.info(
                'Authorize: %s %s %s %s', user, action, resource, resource_id
            )

            proid = None
            if resource_id:
                proid = resource_id.partition('.')[0]

            why = []
            for group_template in groups:
                group_name = _group(
                    group_template,
                    action=action,
                    resource=resource,
                    proid=proid
                )
                _LOGGER.info('Check authorization group: %s', group_name)

                try:
                    group = grp.getgrnam(group_name)
                    username = user.partition('@')[0]
                    members = group.gr_mem
                    _LOGGER.info(
                        'Authorized: User %s is member of %s.',
                        username,
                        group_name
                    )

                    if username in members:
                        return True, why
                    else:
                        why.append(
                            '{} not member of {}'.format(
                                username,
                                group_name
                            )
                        )
                except KeyError:
                    _LOGGER.info('Group does not exist: %s', group_name)
                    why.append('no such group: {}'.format(group_name))

            return False, why

        self.authorize = authorize
