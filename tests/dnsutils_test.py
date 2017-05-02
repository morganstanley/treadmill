"""Unit test for treadmill.dnsutils
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

from treadmill import dnsutils


class DnsutilsTest(unittest.TestCase):
    """treadmill.dnsutils tests."""

    def test_srv_rec_to_url(self):
        """Test srv_rec_to_url method with no protocol"""
        srv_rec = ('host', 1234, None, None)
        url = dnsutils.srv_rec_to_url(srv_rec)
        self.assertEquals(url, '://host:1234')

    def test_srv_rec_to_url_target(self):
        """Test srv_rec_to_url method with target name"""
        srv_target = '_protocol.x.y.z'
        srv_rec = ('host', 1234, None, None)
        url = dnsutils.srv_rec_to_url(srv_rec, srv_target)
        self.assertEquals(url, 'protocol://host:1234')

    def test_srv_rec_to_url_proto(self):
        """Test srv_rec_to_url method with protocol argument"""
        srv_rec = ('host', 1234, None, None)
        proto = 'myproto'
        url = dnsutils.srv_rec_to_url(srv_rec, protocol=proto)
        self.assertEquals(url, '{}://host:1234'.format(proto))

    def test_srv_rec_to_url_both(self):
        """Test srv_rec_to_url method with both optional arguments"""
        srv_target = '_protocol.x.y.z'
        srv_rec = ('host', 1234, None, None)
        proto = 'myproto'
        url = dnsutils.srv_rec_to_url(srv_rec, srv_target, protocol=proto)
        self.assertEquals(url, '{}://host:1234'.format(proto))


if __name__ == '__main__':
    unittest.main()
