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


_URL = 'Plugin.Activate'


def init(api, cors, impl):
    """Configures REST handlers for docker authz resource."""
    del cors
    namespace = api.namespace(
        _URL, description='Docker authz plugin activate call'
    )

    # only /Plugin.Activate allowd, /Plugin.Activate/ not allowed
    @namespace.route('')
    class _Activate(restplus.Resource):
        """Treadmill docker authz plugin activate resource"""

        def post(self):
            """Returns plugin name monitors."""
            status = http.client.OK
            return flask.Response(
                json.dumps(impl.activate()),
                status=status,
                mimetype='application/json'
            )

    # return URL explicitly because there is '.' in URL
    return _URL
