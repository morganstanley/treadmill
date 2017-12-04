"""Treadmill DNS REST api.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_restplus as restplus
from flask_restplus import fields

from treadmill import webutils


def init(api, cors, impl):
    """Configures REST handlers for DNS resource."""

    namespace = webutils.namespace(
        api, __name__, 'DNS REST operations'
    )

    server_model = fields.String(description='Server')

    model = {
        '_id': fields.String(
            description='Name',
            max_length=32),
        'location': fields.String(description='Location'),
        'nameservers': fields.List(server_model),
        'rest-server': fields.List(server_model),
        'zkurl': fields.String(description='Zookeeper URL'),
        'fqdn': fields.String(description='FQDN'),
        'ttl': fields.String(description='Time To Live'),
    }

    dns_model = api.model(
        'DNS', model
    )

    @namespace.route('/')
    class _DNSList(restplus.Resource):
        """Treadmill DNS resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=dns_model)
        def get(self):
            """Returns list of configured DNS servers."""
            return impl.list()

    @namespace.route('/<dns>')
    @api.doc(params={'dns': 'DNS ID/name or FQDN'})
    class _DNSResource(restplus.Resource):
        """Treadmill DNS resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=dns_model)
        def get(self, dns):
            """Return Treadmill cell configuration."""
            return impl.get(dns)
