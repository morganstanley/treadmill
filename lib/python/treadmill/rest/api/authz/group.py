"""Treadmill group authorization REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill.rest.api.authz import authz_base


def init(api, cors, impl):
    """Configures REST handlers for cron resource."""
    del cors

    class _AuthZ(authz_base.AuthzAPIBase):
        """Treadmill Group authorizer."""

        def __init__(self, api, *args, **kwargs):
            super(_AuthZ, self).__init__(impl, api, *args, **kwargs)

    authz_base.register_authz_resource(_AuthZ, api, 'Group based authorizer')
