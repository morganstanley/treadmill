"""
Unit test for Treadmill http module.
"""

import unittest

from treadmill import http


class HttpTest(unittest.TestCase):
    """Test for treadmill.http."""

    def test_search(self):
        """Tests http request construction."""
        req = http.make_request('http://xxx', 'GET', None, None)
        self.assertIsNone(req.data)

        req = http.make_request('http://xxx', 'GET', 'ignored', None)
        self.assertIsNone(req.data)

        req = http.make_request('http://xxx', 'DELETE', None, None)
        self.assertIsNone(req.data)

        req = http.make_request('http://xxx', 'DELETE', 'ignored', None)
        self.assertIsNone(req.data)

        req = http.make_request('http://xxx', 'POST', '', None)
        self.assertEqual(0, len(req.data))

        req = http.make_request('http://xxx', 'POST', 'abc', None)
        self.assertEqual(3, len(req.data))

        req = http.make_request('http://xxx', 'POST', '', [('xxx', 'yyy'),
                                                           ('foo',)])

        self.assertEqual('yyy', req.get_header('Xxx'))
        self.assertEqual('1', req.get_header('Foo'))


if __name__ == '__main__':
    unittest.main()
