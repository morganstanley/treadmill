"""Tenant API tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill.api import tenant


class ApiTenantTest(unittest.TestCase):
    """treadmill.api.tenant tests."""

    def setUp(self):
        self.tnt = tenant.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock()))
    def test_list(self):
        """Dummy test for treadmill.api.tenant._list()"""
        tnt_admin = treadmill.context.AdminContext.tenant.return_value
        tnt_admin.list.return_value = []
        self.tnt.list()
        self.assertTrue(tnt_admin.list.called)

    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'tenant': '111'}
                })))
    def test_get(self):
        """Dummy test for treadmill.api.tenant.get()"""
        tnt_admin = treadmill.context.AdminContext.tenant.return_value
        self.tnt.get('some_tenant')
        tnt_admin.get.assert_called_with('some_tenant')

    @mock.patch('treadmill.context.AdminContext.tenant',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'tenant': '111'},
                    'create.return_value': mock.Mock()
                })))
    def test_create(self):
        """Dummy test for treadmill.api.tenant.create()"""
        tnt_admin = treadmill.context.AdminContext.tenant.return_value
        self.tnt.create('some_tenant', {'systems': [1, 2, 3]})
        tnt_admin.get.assert_called_with('some_tenant', dirty=True)


if __name__ == '__main__':
    unittest.main()
