"""Treadmill Server REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for server resource."""

    namespace = webutils.namespace(api, __name__, 'Server REST operations')

    req_parser = api.parser()
    req_parser.add_argument('cell', help='Cell',
                            location='args', required=False)
    req_parser.add_argument('partition', help='Partition',
                            location='args', required=False)

    @namespace.route('/',)
    class _ServerList(restplus.Resource):
        """Treadmill Server resource"""

        @webutils.get_api(api, cors, parser=req_parser)
        def get(self):
            """Returns list of configured servers."""
            args = req_parser.parse_args()
            return impl.list(args.get('cell'), args.get('partition'))

    @namespace.route('/<server_id>')
    class _ServerResource(restplus.Resource):
        """Treadmill Server resource."""

        @webutils.get_api(api, cors)
        def get(self, server_id):
            """Return Treadmill server configuration."""
            return impl.get(server_id)

        @webutils.delete_api(api, cors)
        def delete(self, server_id):
            """Deletes Treadmill server."""
            return impl.delete(server_id)

        @webutils.put_api(api, cors)
        def put(self, server_id):
            """Updates Treadmill server configuration."""
            return impl.update(server_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, server_id):
            """Creates Treadmill server."""
            return impl.create(server_id, flask.request.json)
