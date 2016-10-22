"""
Treadmill Endpoint REST api.
"""
from __future__ import absolute_import

# For some reason pylint complains about restplus not being able to import.
#
# pylint: disable=E0611,F0401
import flask.ext.restplus as restplus

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for endpoint resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'State REST operations'
    )

    @namespace.route(
        '/<pattern>',
    )
    class _EndpointList(restplus.Resource):
        """Treadmill State resource"""

        @webutils.get_api(api, cors)
        def get(self, pattern):
            """Return all state."""
            return impl.list(pattern, None)

    @namespace.route('/<pattern>/<proto>/<endpoint>')
    class _EndpointResource(restplus.Resource):
        """Treadmill State resource."""

        @webutils.get_api(api, cors)
        def get(self, pattern, proto, endpoint):
            """Return Treadmill instance state."""
            return impl.list(pattern, proto, endpoint)
