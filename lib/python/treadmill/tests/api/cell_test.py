"""Cell API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import admin
from treadmill.api import cell


class ApiCellTest(unittest.TestCase):
    """treadmill.api.cell tests."""

    def setUp(self):
        self.cell = cell.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.list', mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.cell._list()"""
        self.cell.list()
        cell_admin = admin.Cell(None)
        self.assertTrue(cell_admin.list.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'cell': 'ny-999-cell'}))
    def test_get(self):
        """Dummy test for treadmill.api.cell.get()"""
        cell_admin = admin.Cell(None)
        self.cell.get('some-cell')
        cell_admin.get.assert_called_with('some-cell')

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'cell': 'ny-999-cell'}))
    @mock.patch('treadmill.admin.Cell.create', mock.Mock())
    def test_create(self):
        """Dummy test for treadmill.api.cell.create()"""
        cell_admin = admin.Cell(None)
        self.cell.create('some-cell', {'location': 'ny',
                                       'treadmillid': 'treadmld',
                                       'version': 'v3'})
        cell_admin.get.assert_called_with('some-cell', dirty=True)


if __name__ == '__main__':
    unittest.main()
