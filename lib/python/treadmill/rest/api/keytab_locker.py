"""Treadmill Keytab Locker REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_restplus as restplus

from treadmill import webutils


def init(api, _cors, impl):
    """Configures REST handlers for keytab resource."""

    namespace = webutils.namespace(
        api, __name__, 'Keytab Locker REST operations'
    )

    @namespace.route('/')
    class _KeytabList(restplus.Resource):
        """Treadmill Keytab list resource"""

        def get(self):
            """Returns list of available keytabs."""
            return impl.list()
