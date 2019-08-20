"""Treadmill Ticket Locker REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask
import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for cell resource."""

    namespace = webutils.namespace(
        api, __name__, 'Ticket Locker REST operations'
    )

    model = {
        'expires_at': fields.Integer(description='Ticket expiration time.'),
    }

    resp_model = api.model(
        'Ticket', model
    )

    @namespace.route('/')
    class _TicketsList(restplus.Resource):
        """Treadmill Ticket list resource"""

        def get(self):
            """Returns list of available tickets."""
            return impl.list()

    @namespace.route('/@')
    class _TickeUserResource(restplus.Resource):
        """Treadmill Ticket resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=resp_model)
        def get(self):
            """Return Treadmill Ticket details for the authenticated user."""
            return impl.get(flask.g.get('user'))

    @namespace.route('/<principal>')
    @api.doc(params={'principal': 'Principal name'})
    class _TicketResource(restplus.Resource):
        """Treadmill Ticket resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=resp_model)
        def get(self, principal):
            """Return Treadmill Ticket details."""
            return impl.get(principal)
