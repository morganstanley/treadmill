"""Treadmill docker authz service
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import logging
import json
import pwd

import flask

from treadmill.docker_authz import plugins

_LOGGER = logging.getLogger(__name__)

_PLUGIN_NAME = 'authz'


def _get_user_uid_gid(username):
    user_pw = pwd.getpwnam(username)
    return (user_pw.pw_uid, user_pw.pw_gid)


class Server():
    """http server for docker authz plugin service"""

    def __init__(self, *users):
        self.app = flask.Flask(__name__)
        users = [_get_user_uid_gid(user) for user in users]
        _LOGGER.debug('Allowed uid, gid: %r', users)

        self._plugins = [
            plugins.DockerInspectUserPlugin(),
            plugins.DockerRunUserPlugin(users),
            plugins.DockerExecUserPlugin(users),
        ]

        @self.app.route('/AuthZPlugin.AuthZRes', methods=['POST'])
        def authz_res():
            """Handler for response authorization check
            """
            status = 200
            msg = plugins.DEFAULT_ALLOW_MSG

            data = json.loads(flask.request.data.decode())
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
                (status, msg) = plugin.run_res(
                    data['RequestMethod'], data['RequestUri'],
                    request_obj, response_obj,
                )

                if status > 299:
                    allow = False
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

            return flask.Response(
                json.dumps({'Allow': True, 'Msg': msg}),
                status=status,
                mimetype='application/json'
            )

        @self.app.route('/AuthZPlugin.AuthZReq', methods=['POST'])
        def authz_req():
            """Handler for request authorization check
            """
            status = 200
            msg = plugins.DEFAULT_ALLOW_MSG

            data = json.loads(flask.request.data.decode())
            if 'RequestBody' in data:
                request_body = base64.b64decode(data['RequestBody'])
                _LOGGER.debug('request body: %s', request_body)
                request_obj = json.loads(request_body.decode())
            else:
                request_obj = {}

            for plugin in self._plugins:
                (status, msg) = plugin.run_req(
                    data['RequestMethod'], data['RequestUri'], request_obj
                )

                if status > 299:
                    allow = False
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

            return flask.Response(
                json.dumps({'Allow': allow, 'Msg': msg}),
                status=status,
                mimetype='application/json'
            )

        @self.app.route('/Plugin.Activate', methods=['POST'])
        def plugin_activate():
            """For query what kind of docker plugin we provide
            dockerd should starts with --authorization-plugin=authz
            This method must be POST.
            """
            return flask.Response(
                json.dumps({'Implements': [_PLUGIN_NAME]}),
                status=200,
                mimetype='application/json'
            )
