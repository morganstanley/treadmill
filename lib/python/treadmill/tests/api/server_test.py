"""Server API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill.api import server


class ApiServerTest(unittest.TestCase):
    """treadmill.api.server tests."""

    def setUp(self):
        self.svr = server.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.server',
                mock.Mock(return_value=mock.Mock(**{
                    'list.return_value': []
                })))
    def test_list(self):
        """Dummy test for treadmill.api.server._list()"""
        self.svr.list(None, None)
        svr_admin = treadmill.context.AdminContext.server.return_value
        self.assertTrue(svr_admin.list.called)

        self.svr.list('some-cell', None)
        svr_admin.list.assert_called_with({'cell': 'some-cell'})

        self.svr.list(partition='xxx')
        svr_admin.list.assert_called_with({})

        self.svr.list('some-cell', 'xxx')
        svr_admin.list.assert_called_with({'cell': 'some-cell'})

    @mock.patch('treadmill.context.AdminContext.server',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'_id': 'foo.somewhere.in.xx.com'}
                })))
    def test_get(self):
        """Dummy test for treadmill.api.server.get()"""
        svr_admin = treadmill.context.AdminContext.server.return_value
        self.svr.get('foo.somewhere.in.xx.com')
        svr_admin.get.assert_called_with('foo.somewhere.in.xx.com')

    @mock.patch('treadmill.context.AdminContext.server',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {'_id': 'foo.somewhere.in.xx.com'},
                    'create.return_value': mock.Mock(),
                })))
    def test_create(self):
        """Dummy test for treadmill.api.server.create()"""
        svr_admin = treadmill.context.AdminContext.server.return_value
        self.svr.create('foo.somewhere.in.xx.com', {'cell': 'ny-999-cell',
                                                    'partition': 'xxx'})
        svr_admin.get.assert_called_with('foo.somewhere.in.xx.com', dirty=True)


if __name__ == '__main__':
    unittest.main()
