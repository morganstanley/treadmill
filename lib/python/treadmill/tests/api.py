"""
Verifies cell API.
"""

import unittest
import logging

from treadmill import context
from treadmill import zknamespace as z
from treadmill import tests as chk


_LOGGER = logging.getLogger(__name__)


def _to_hostport(url):
    """Convert *://host:port into (host, port) tuple."""
    return tuple(url[url.find('://') + 3:].split(':'))


def _thiscell(url):
    """Check url host belongs to the cell."""
    host, _port = _to_hostport(url)
    zkclient = context.GLOBAL.zk.conn
    return zkclient.exists(z.path.server(host))


def srv_records_test(cls, name, urls):
    """API srv records test."""

    def test_count(self):
        """Checks api srv records count > 0."""
        print 'urls:', urls
        self.assertTrue(len(urls) > 0)

    test_count.__doc__ = ''
    chk.add_test(cls, test_count, '{} count is ok', name)


def api_test(cls, name, url):
    """Tests api."""

    def test_is_up(self):
        """Test api host/port is up."""
        print url
        host, port = _to_hostport(url)
        self.assertTrue(chk.connect(host, port))

    def test_is_ok(self):
        """Test api health."""
        print url
        self.assertTrue(chk.url_check(url))

    test_is_ok.__doc__ = url
    test_is_up.__doc__ = url

    chk.add_test(cls, test_is_up, '{} is up', name)
    chk.add_test(cls, test_is_ok, '{} is ok', name)


def test():
    """Check system API."""

    adminapi = [url for url in context.GLOBAL.admin_api(None)
                if _thiscell(url)]
    cellapi = context.GLOBAL.cell_api(None)
    stateapi = context.GLOBAL.state_api(None)
    wsapi = context.GLOBAL.ws_api(None)

    class APITest(unittest.TestCase):
        """API Test."""

    for name, urls in [('adminapi', adminapi),
                       ('cellapi', cellapi),
                       ('stateapi', stateapi),
                       ('wsapi', wsapi)]:
        srv_records_test(APITest, name, urls)
        for url in urls:
            api_test(APITest, name, url)

    return APITest
