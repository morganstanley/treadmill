"""
Treadmill State REST api.
"""
from __future__ import absolute_import

import httplib

import flask
import flask_restplus as restplus

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for state resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'State REST operations'
    )

    @namespace.route(
        '/',
    )
    class _StateList(restplus.Resource):
        """Treadmill State resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Return all state."""
            return impl.list(flask.request.args.get('match'))

        @webutils.put_api(api, cors)
        def post(self):
            """Returns state of the instance list."""
            instances = flask.request.json.get('instances')
            states = [impl.get(instance_id) for instance_id in instances]
            return [state for state in states if state is not None]

    @namespace.route('/<instance_id>')
    class _StateResource(restplus.Resource):
        """Treadmill State resource."""

        @webutils.get_api(api, cors)
        def get(self, instance_id):
            """Return Treadmill instance state."""
            state = impl.get(instance_id)
            if state is None:
                api.abort(httplib.NOT_FOUND,
                          'Instance does not exist: %s' % instance_id)
            return state
