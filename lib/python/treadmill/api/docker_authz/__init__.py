"""Treadmill docker authz service
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import json
import logging

from treadmill import utils
from treadmill.api.docker_authz import plugins

_LOGGER = logging.getLogger(__name__)

_PLUGIN_NAME = 'authz'


class API:
    """API of docker authz plugin
    """

    _plugins = [
        plugins.DockerInspectUserPlugin(),
        plugins.DockerRunUserPlugin(),
        plugins.DockerExecUserPlugin(),
    ]

    def __init__(self, **kwargs):
        users = kwargs.get('users', [])
        self._users = [utils.get_uid_gid(user) for user in users]
        _LOGGER.debug('Allowed uid, gid: %r', self._users)

        # TODO: add schema validation
        def authzreq(data):
            """implement AuthZPlugin.AuthZReq
            """
            if 'RequestBody' in data:
                request_body = base64.b64decode(data['RequestBody'])
                _LOGGER.debug('request body: %s', request_body)
                request_obj = json.loads(request_body.decode())
            else:
                request_obj = {}

            for plugin in self._plugins:
                (allow, msg) = plugin.run_req(
                    data['RequestMethod'], data['RequestUri'], request_obj,
                    users=self._users
                )

                if not allow:
                    break
            else:
                allow = True

            _LOGGER.info(
                'Request: %s %s %s (%s)',
                data['RequestMethod'],
                data['RequestUri'],
                ('Authorized' if allow else 'Not authorized'),
                msg,
            )

            return (allow, msg)

        # TODO: add schema validation
        def authzres(data):
            """implement AuthZPlugin.AuthZReq
            """
            if 'RequestBody' in data:
                request_body = base64.b64decode(data['RequestBody'])
                _LOGGER.debug('request body: %s', request_body)
                request_obj = json.loads(request_body.decode())
            else:
                request_obj = {}

            if 'ResponseBody' in data:
                response_body = base64.b64decode(data['ResponseBody'])
                _LOGGER.debug('response body: %s', response_body)
                response_obj = json.loads(response_body.decode())
            else:
                response_obj = {}

            for plugin in self._plugins:
                (allow, msg) = plugin.run_res(
                    data['RequestMethod'], data['RequestUri'],
                    request_obj, response_obj,
                    users=self._users,
                )

                if not allow:
                    break
            else:
                allow = True

            _LOGGER.info(
                'Response: %s %s %s %s',
                data['RequestMethod'],
                data['RequestUri'],
                data.get('ResponseStatusCode', None),
                ('Authorized' if allow else 'Not authorized'),
            )

            return (allow, msg)

        # TODO: add schema validation
        def activate():
            """Implement Plugin.Activate
            """
            return {
                'Implements': [_PLUGIN_NAME]
            }

        self.authzreq = authzreq
        self.authzres = authzres
        self.activate = activate
