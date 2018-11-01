"""Implementation of group based authorization API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import grp      # pylint: disable=import-error
import logging
import pwd      # pylint: disable=import-error
import os

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

        exclude = kwargs.get('exclude', {})
        _LOGGER.info('Unrestricted whitelist: %s', exclude)

        me = pwd.getpwuid(os.getuid())[0]

        # TODO: add schema validation.
        def authorize(user, action, resource, payload):
            """Authorize user/action/resource"""

            resource_id = payload.get('pk')

            _LOGGER.info(
                'Authorize: %s %s %s %s', user, action, resource, resource_id
            )

            if '{}:{}'.format(resource, action) in exclude:
                _LOGGER.info(
                    'Access allowed based on exclusion whitelist: %s:%s',
                    action,
                    resource
                )
                return True, []

            username = user.partition('@')[0]

            # Special rule - authorize self.
            if username == me:
                _LOGGER.info('Authorized self: %s', username)
                return True, []

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
