"""Local node redirect REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from six.moves import http_client

import flask
import flask_restplus as restplus

from treadmill import webutils
from treadmill import utils


def init(api, _cors, impl):
    """Configures REST handlers for allocation resource."""

    namespace = webutils.namespace(
        api, __name__, 'Local nodeinfo redirect API.'
    )

    @namespace.route('/<hostname>/<path:path>')
    class _NodeRedirect(restplus.Resource):
        """Redirects to local nodeinfo endpoint."""

        def get(self, hostname, path):
            """Returns list of local instances."""
            hostport = impl.get(hostname)
            if not hostport:
                return 'Host not found.', http_client.NOT_FOUND

            url = utils.encode_uri_parts(path)
            return flask.redirect('http://%s/%s' % (hostport, url),
                                  code=http_client.FOUND)
