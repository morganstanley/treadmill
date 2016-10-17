"""
Treadmill Cell REST api.
"""
from __future__ import absolute_import

# pylint: disable=E0611,F0401
import flask.ext.restplus as restplus
import flask

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for cell resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cell REST operations'
    )

    @namespace.route('/')
    class _CellList(restplus.Resource):
        """Treadmill Cell resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured cells."""
            return impl.list()

    @namespace.route('/<cell_id>')
    class _CellResource(restplus.Resource):
        """Treadmill Cell resource."""

        @webutils.get_api(api, cors)
        def get(self, cell_id):
            """Return Treadmill cell configuration."""
            return impl.get(cell_id)

        @webutils.delete_api(api, cors)
        def delete(self, cell_id):
            """Deletes Treadmill cell."""
            return impl.delete(cell_id)

        @webutils.put_api(api, cors)
        def put(self, cell_id):
            """Updates Treadmill cell configuration."""
            return impl.update(cell_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, cell_id):
            """Creates Treadmill cell."""
            return impl.create(cell_id, flask.request.json)
