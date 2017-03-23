"""Unit test for treadmill.dnsutils
"""

import unittest

from treadmill import dnsutils


class DnsutilsTest(unittest.TestCase):
    """treadmill.dnsutils tests."""

    def test_srv_target_to_url(self):
        """Test srv_target_to_url method"""
        srv_rec = '_protocol.x.y.z'
        srv_target = ('host', 1234, None, None)
        url = dnsutils.srv_target_to_url(srv_rec, srv_target)
        self.assertEqual(url, 'protocol://host:1234')


if __name__ == '__main__':
    unittest.main()
