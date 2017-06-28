"""Verifies cell API.
"""

import unittest
import logging

from treadmill import cli
from treadmill import context
from treadmill import zknamespace as z
from treadmill import checkout as chk


_LOGGER = logging.getLogger(__name__)


def _to_hostport(url):
    """Convert *://host:port into (host, port) tuple."""
    return tuple(url[url.find('://') + 3:].split(':'))


def _thiscell(url):
    """Check url host belongs to the cell."""
    host, _port = _to_hostport(url)
    zkclient = context.GLOBAL.zk.conn
    return zkclient.exists(z.path.server(host))


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

        for url in urls:

            @chk.T(APITest, url=url, name=name)
            def _test_is_up(self, url, name):
                """Test {name} - {url} is up."""
                del name
                cli.out(url)
                host, port = _to_hostport(url)
                self.assertTrue(chk.connect(host, port))

            @chk.T(APITest, url=url, name=name)
            def _test_is_ok(self, url, name):
                """Test {name} - {url} is healthy."""
                del name
                cli.out(url)
                self.assertTrue(chk.url_check(url))

    return APITest
