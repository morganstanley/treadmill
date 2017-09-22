"""Verifies cell API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import logging

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import zknamespace as z
from treadmill import checkout as chk


_LOGGER = logging.getLogger(__name__)

_API_LOOKUP_BASE = 'http://{MASTER}:5800/api-lookup'


def _to_hostport(url):
    """Convert *://host:port into (host, port) tuple."""
    return tuple(urllib_parse.urlparse(url).netloc.split(':'))


def _thiscell(url):
    """Check url host belongs to the cell."""
    host, _port = _to_hostport(url)
    zkclient = context.GLOBAL.zk.conn
    return zkclient.exists(z.path.server(host))


def _parse_response(resp):
    """Parse rest response"""
    return [(target['host'], str(target['port']))
            for target in resp.json()['targets']]


def _masters():
    """Get masters"""
    hostports = context.GLOBAL.zk.url.split('@')[1].split('/')[0]
    return [item.split(':')[0] for item in hostports.split(',')]


def test():
    """Check system API."""

    try:
        adminapi = [url for url in context.GLOBAL.admin_api(None)
                    if _thiscell(url)]
    except context.ContextError:
        adminapi = []

    try:
        cellapi = context.GLOBAL.cell_api(None)
    except context.ContextError:
        cellapi = []

    try:
        stateapi = context.GLOBAL.state_api(None)
    except context.ContextError:
        stateapi = []

    try:
        wsapi = context.GLOBAL.ws_api(None)
    except context.ContextError:
        wsapi = []

    class APITest(unittest.TestCase):
        """API Test."""

    for name, urls in [('adminapi', adminapi),
                       ('cellapi', cellapi),
                       ('stateapi', stateapi),
                       ('wsapi', wsapi)]:
        @chk.T(APITest, urls=urls, name=name)
        def _test_count(self, urls, name):
            """Checks {name} srv records count > 0."""
            cli.out('%s: %r' % (name, urls))
            self.assertTrue(len(urls) > 0)

        @chk.T(APITest, urls=urls, name=name)
        def _test_api_lookup(self, urls, name):
            """Test api lookup"""
            dns_result = [_to_hostport(url) for url in urls]
            for master in _masters():
                api_lookup_url = _API_LOOKUP_BASE.format(MASTER=master)
                cli.out('Api lookup : {} on {}'.format(name, master))
                if name == 'adminapi':
                    resp = restclient.get(
                        api_lookup_url,
                        '/{}'.format(name),
                        retries=0
                    )
                    rest_result = _parse_response(resp)
                    self.assertTrue(all(x in rest_result for x in dns_result))
                else:
                    resp = restclient.get(
                        api_lookup_url,
                        '/{}/{}'.format(name, context.GLOBAL.cell),
                        retries=0
                    )
                    rest_result = _parse_response(resp)
                    self.assertTrue(sorted(rest_result) == sorted(dns_result))

        for url in urls:

            @chk.T(APITest, url=url, name=name)
            def _test_is_up(self, url, name):
                """Test {name} - {url} is up."""
                del name
                cli.out(' Server up : {}'.format(url))
                host, port = _to_hostport(url)
                self.assertTrue(chk.connect(host, port))

            @chk.T(APITest, url=url, name=name)
            def _test_is_ok(self, url, name):
                """Test {name} - {url} is healthy."""
                del name
                cli.out(' Server healthy : {}'.format(url))
                self.assertTrue(chk.url_check(url))

    return APITest
