"""Authorization for Treadmill API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import decorator

# Disable E0611: No 'name' in module
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Authorization error."""

    def __init__(self, annotations):
        self.annotations = annotations
        super(AuthorizationError, self).__init__('\n'.join(self.annotations))


class NullAuthorizer(object):
    """Passthrough authorization class."""

    def __init__(self):
        pass

    def authorize(self, _resource, _action, _args, _kwargs):
        """Null authorization - always succeeds."""
        pass


class ClientAuthorizer(object):
    """Loads authorizer implementation plugin."""

    def __init__(self, user_clbk, auth=None):
        self.user_clbk = user_clbk
        self.remote = auth

    def authorize(self, resource, action, args, _kwargs):
        """Delegate authorization to the plugin."""
        resource = resource.split('.').pop()

        user = self.user_clbk()
        # PGE API can't handle None.
        if user is None:
            user = ''

        # Defaults for primary key and payload.
        url = '/%s/%s/%s' % (user, action, resource)
        data = {}

        if len(args) > 0:
            data['pk'] = str(args[0])
        if len(args) > 1:
            data['payload'] = args[1]

        # POST http://auth_server/user/action/resource
        # {"pk": "foo", "payload": { ... }}
        response = restclient.post(api=self.remote,
                                   url=url,
                                   payload=data,
                                   auth=None)
        authd = response.json()
        _LOGGER.debug('client authorize ressult %r', authd)

        if not authd['auth']:
            raise AuthorizationError(authd['annotations'])

        return authd


def authorize(authorizer):
    """Constructs authorizer decorator."""

    @decorator.decorator
    def decorated(func, *args, **kwargs):
        """Decorated function."""
        action = getattr(func, 'auth_action', func.__name__.strip('_'))
        resource = getattr(func, 'auth_resource', func.__module__.strip('_'))
        _LOGGER.debug('Authorize: %s %s %r %r', resource, action, args, kwargs)
        authorizer.authorize(resource, action, args, kwargs)
        return func(*args, **kwargs)

    return decorated


def wrap(api, authorizer):
    """Returns module API wrapped with authorizer function."""
    for action in dir(api):
        if action.startswith('_'):
            continue

        if authorizer:
            auth = authorize(authorizer)
            attr = getattr(api, action)
            if hasattr(attr, '__call__'):
                setattr(api, action, auth(attr))
            elif hasattr(attr, '__init__'):
                setattr(api, action, wrap(attr, authorizer))
            else:
                _LOGGER.want('unknown attribute type: %r, %s', api, action)

    return api
