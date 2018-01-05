"""Dyndns REST client.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import restclient

_LOGGER = logging.getLogger(__name__)


class DyndnsClient(object):
    """Helper class to call DynDNS."""

    def __init__(self, dyndns_servers):
        self.api = ['http://%s' % server for server in dyndns_servers]

    def get(self, endpoint):
        """Make a get request to DynDNS REST server."""
        url = '/v1/' + endpoint
        resp = restclient.get(self.api, url)
        return resp.json()

    def post(self, endpoint, **kwargs):
        """Make a post request to DynDNS REST server."""
        url = '/v1/' + endpoint
        resp = restclient.post(self.api, url, payload=kwargs)
        return resp.json()

    def delete(self, endpoint, **kwargs):
        """Make delete request to DynDNS REST server."""
        url = '/v1/' + endpoint
        restclient.delete(self.api, url, payload=kwargs)
