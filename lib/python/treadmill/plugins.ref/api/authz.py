"""Authorization plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import authz


class _Authorizer(object):
    """Authorizer."""

    def __init__(self, user_clbk):
        pass

    def authorize(self, resource, action, args, _kwargs):
        """Authorize user/resource/action."""
        del resource
        del action
        del args

        authorized = True
        if not authorized:
            raise authz.AuthorizationError('some reason.')


def init(user_clbk):
    """Initialize the authorizer."""
    return _Authorizer(user_clbk)
