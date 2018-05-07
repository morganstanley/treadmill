"""Tenant API tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import admin
from treadmill.api import tenant


class ApiTenantTest(unittest.TestCase):
    """treadmill.api.tenant tests."""

    def setUp(self):
        self.tnt = tenant.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Tenant.list', mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.tenant._list()"""
        self.tnt.list()
        tnt_admin = admin.Tenant(None)
        self.assertTrue(tnt_admin.list.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Tenant.get',
                mock.Mock(return_value={'tenant': '111'}))
    def test_get(self):
        """Dummy test for treadmill.api.tenant.get()"""
        tnt_admin = admin.Tenant(None)
        self.tnt.get('some_tenant')
        tnt_admin.get.assert_called_with('some_tenant')

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Tenant.get',
                mock.Mock(return_value={'tenant': '111'}))
    @mock.patch('treadmill.admin.Tenant.create', mock.Mock())
    def test_create(self):
        """Dummy test for treadmill.api.tenant.create()"""
        tnt_admin = admin.Tenant(None)
        self.tnt.create('some_tenant', {'systems': [1, 2, 3]})
        tnt_admin.get.assert_called_with('some_tenant', dirty=True)


if __name__ == '__main__':
    unittest.main()
