"""Treadmill docker authz REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import http.client

import flask
import flask_restplus as restplus


_URL = 'AuthZPlugin.AuthZRes'


def init(api, cors, impl):
    """Configures REST handlers for docker authz resource."""
    del cors

    namespace = api.namespace(
        _URL, description='Docker authz plugin authz response call'
    )

    # authz plugin does not accept tailing '/'
    @namespace.route('')
    class _Authz(restplus.Resource):
        """Treadmill App monitor resource"""

        def post(self):
            """Returns list of configured app monitors."""
            status = http.client.OK
            payload = flask.request.get_json(force=True)

            (allow, msg) = impl.authzres(payload)

            return flask.Response(
                json.dumps({'allow': allow, 'msg': msg}),
                status=status,
                mimetype='application/json'
            )

    # return URL explicitly because there is '.' in URL
    return _URL
