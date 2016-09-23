"""
Treadmill App REST api.
"""
from __future__ import absolute_import

# For some reason pylint complains about restplus not being able to import.
#
# pylint: disable=E0611,F0401
import flask.ext.restplus as restplus
import flask

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for app resource."""

    namespace = webutils.namespace(
        api, __name__, 'Application REST operations'
    )

    @namespace.route(
        '/',
    )
    class _AppList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured applications."""
            return impl.list()

    @namespace.route('/<app_id>')
    class _AppResource(restplus.Resource):
        """Treadmill App resource."""

        @webutils.get_api(api, cors)
        def get(self, app_id):
            """Return Treadmill application configuration."""
            return impl.get(app_id)

        @webutils.delete_api(api, cors)
        def delete(self, app_id):
            """Deletes Treadmill application."""
            return impl.delete(app_id)

        @webutils.put_api(api, cors)
        def put(self, app_id):
            """Updates Treadmill application configuration."""
            return impl.update(app_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, app_id):
            """Creates Treadmill application."""
            return impl.create(app_id, flask.request.json)
