"""DNS API tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import admin
from treadmill.api import dns


class ApiDNSTest(unittest.TestCase):
    """treadmill.api.dns tests."""

    def setUp(self):
        self.dns = dns.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.DNS.list', mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.cell._list()"""
        self.dns.list()
        dns_admin = admin.DNS(None)
        self.assertTrue(dns_admin.list.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.DNS.get',
                mock.Mock(return_value={'location': 'as'}))
    def test_get(self):
        """Dummy test for treadmill.api.cell.get()"""
        dns_admin = admin.DNS(None)
        self.dns.get('as')
        dns_admin.get.assert_called_with('as')


if __name__ == '__main__':
    unittest.main()
