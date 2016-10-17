"""
Treadmill AppGroup REST api.
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
    """Configures REST handlers for app_group resource."""

    namespace = webutils.namespace(
        api, __name__, 'AppGroup REST operations'
    )

    @namespace.route(
        '/',
    )
    class _AppGroupList(restplus.Resource):
        """Treadmill App resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured applications."""
            return impl.list()

    @namespace.route('/<app_group_id>')
    class _AppGroupResource(restplus.Resource):
        """Treadmill AppGroup resource."""

        @webutils.get_api(api, cors)
        def get(self, app_group_id):
            """Return Treadmill app-group configuration."""
            return impl.get(app_group_id)

        @webutils.delete_api(api, cors)
        def delete(self, app_group_id):
            """Deletes Treadmill app-group."""
            return impl.delete(app_group_id)

        @webutils.put_api(api, cors)
        def put(self, app_group_id):
            """Updates Treadmill app-group configuration."""
            return impl.update(app_group_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, app_group_id):
            """Creates Treadmill app-group."""
            return impl.create(app_group_id, flask.request.json)
