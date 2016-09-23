"""
Unit test for Treadmill http module.
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

from treadmill import http


class HttpTest(unittest.TestCase):
    """Test for treadmill.http."""

    def test_search(self):
        """Tests http request construction."""
        req = http.make_request('http://xxx', 'GET', None, None)
        self.assertIsNone(req.get_data())

        req = http.make_request('http://xxx', 'GET', 'ignored', None)
        self.assertIsNone(req.get_data())

        req = http.make_request('http://xxx', 'DELETE', None, None)
        self.assertIsNone(req.get_data())

        req = http.make_request('http://xxx', 'DELETE', 'ignored', None)
        self.assertIsNone(req.get_data())

        req = http.make_request('http://xxx', 'POST', '', None)
        self.assertEquals(0, len(req.get_data()))

        req = http.make_request('http://xxx', 'POST', 'abc', None)
        self.assertEquals(3, len(req.get_data()))

        req = http.make_request('http://xxx', 'POST', '', [('xxx', 'yyy'),
                                                           ('foo',)])

        self.assertEquals('yyy', req.get_header('Xxx'))
        self.assertEquals('1', req.get_header('Foo'))


if __name__ == '__main__':
    unittest.main()
