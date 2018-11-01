"""Base authorization API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import json
import http.client

import flask
import flask_restplus as restplus

from treadmill import webutils

_LOGGER = logging.getLogger(__name__)

_ROUTE = '/<user>/<action>/<resource>'


def register_authz_resource(resource, api, description):
    """Register a resource for authz namespace.

    :param resource: sub-class inherited from AuthzAPIBase.

    :param api: reserved parameter for `restplus.Resource`.
    :param description: reserved parameter for `restplus.Resource`.
    """
    namespace = webutils.namespace(api, '', description)
    namespace.add_resource(resource, _ROUTE)


class AuthzAPIBase(restplus.Resource):
    """Base class for authorization API.
    """

    def __init__(self, impl, api, *args, **kwargs):
        """
        :param impl: custom authorizer which should implement a function with
                     signature `authorize(user, action, resource, payload)`.

        :param api: reserved parameter for `restplus.Resource`.
        """
        super(AuthzAPIBase, self).__init__(api, *args, **kwargs)
        self.impl = impl

    def post(self, user, action, resource):
        """Authorize user access to resource."""

        status = http.client.OK
        payload = flask.request.get_json(force=True)

        try:
            authorized, why = self.impl.authorize(
                user, action, resource, payload,
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception('Unhandled exception')
            authorized, why = False, [str(err)]
            status = http.client.INTERNAL_SERVER_ERROR

        _LOGGER.info(
            'Authorize %s %s %s: %s', user, action, resource, authorized,
        )

        return flask.Response(
            json.dumps({'auth': authorized, 'annotations': why}),
            status=status,
            mimetype='application/json',
        )
