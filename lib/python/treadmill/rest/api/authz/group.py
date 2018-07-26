"""Treadmill group authorization REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import http.client
import json

import flask
import flask_restplus as restplus

from treadmill import webutils


_LOGGER = logging.getLogger(__name__)


def init(api, cors, impl):
    """Configures REST handlers for cron resource."""
    del cors
    namespace = webutils.namespace(
        api, '', 'Group based authorizer'
    )

    @namespace.route('/<user>/<action>/<resource>')
    class _AuthZ(restplus.Resource):
        """Treadmill Group authorizer."""

        def post(self, user, action, resource):
            """Authorize user access to resource based on group membership."""

            payload = flask.request.get_json(force=True)

            _LOGGER.info(
                'authorize user: %s, action: %s, resource, %s, payload: %r',
                user, action, resource, payload
            )

            status = http.client.OK
            resource_id = payload.get('pk')
            try:
                authorized, why = impl.authorize(
                    user=user,
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    payload=payload.get('payload')
                )
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception('Unhandled exception')
                authorized, why = False, [str(err)]
                status = http.client.INTERNAL_SERVER_ERROR

            _LOGGER.info(
                'Authorize %s %s %s %s: %s',
                user, action, resource, resource_id, authorized
            )

            # TODO: API returns 200 always, for authorization it will be more
            #       intuitive to return FORBIDDEN
            return flask.Response(
                json.dumps({'auth': authorized, 'annotations': why}),
                status=status,
                mimetype='application/json'
            )
