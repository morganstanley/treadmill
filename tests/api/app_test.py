"""Cell API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock
from jsonschema import exceptions as jexceptions

from treadmill import admin
from treadmill.api import app


class ApiAppTest(unittest.TestCase):
    """treadmill.api.app tests."""

    def setUp(self):
        self.app = app.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Application.list', mock.Mock(return_value=[]))
    def test_list(self):
        """Dummy test for treadmill.api.cell._list()"""
        app_admin = admin.Application(None)
        self.app.list('*')
        self.assertTrue(app_admin.list.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Application.get',
                mock.Mock(return_value={}))
    def test_get(self):
        """Dummy test for treadmill.api.cell.get()"""
        app_admin = admin.Application(None)
        self.app.get('proid.name')
        app_admin.get.assert_called_with('proid.name')

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Application.get',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.Application.create', mock.Mock())
    def test_create(self):
        """Dummy test for treadmill.api.cell.create().
        """
        app_admin = admin.Application(None)
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'tickets': ['a@realm1', 'b@realm2'],
            'features': [],
            'services': [
                {
                    'name': 'a',
                    'command': '/a',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                },
                {
                    'name': 'b',
                    'command': '/b',
                },
            ],
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ],
        }

        self.app.create('proid.name', payload)
        app_admin.create.assert_called_with('proid.name', payload)

    def test_create_fail_null(self):
        """Test treadmill.api.cell.create() fails with null  services.
        """
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'tickets': [u'a@realm1', u'b@realm2'],
            'features': [],
            'services': None,
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ],
        }

        with self.assertRaises(jexceptions.ValidationError):
            self.app.create('proid.name', payload)

    def test_create_fail_empty(self):
        """Test treadmill.api.cell.create() fails with empty list services.
        """
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'tickets': [u'a@realm1', u'b@realm2'],
            'features': [],
            'services': [],
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ],
        }

        with self.assertRaises(jexceptions.ValidationError):
            self.app.create('proid.name', payload)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Application.get',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.Application.create', mock.Mock())
    def test_create_valid_affinity(self):
        """Test valid affinity name for treadmill.api.cell.create().
        """
        app_admin = admin.Application(None)
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'features': [],
            'affinity': 'foo.bar',
            'services': [
                {
                    'name': 'a',
                    'command': '/a',
                },
            ],
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
            ],
        }

        self.app.create('proid.name', payload)
        app_admin.create.assert_called_with('proid.name', payload)

    def test_create_invalid_affinity(self):
        """Test invalid affinity name for treadmill.api.cell.create().
        """
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '1G',
            'features': [],
            'affinity': '/foo.bar',
            'services': [
                {
                    'name': 'a',
                    'command': '/a',
                },
            ],
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
            ],
        }

        with self.assertRaises(jexceptions.ValidationError):
            self.app.create('proid.name', payload)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.admin.Application.get',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.admin.Application.create', mock.Mock())
    def test_create_docker(self):
        """Dummy test for treadmill.api.cell.create() for docker"""
        app_admin = admin.Application(None)
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '20G',
            'image': 'docker://microsoft/windowsservercore',
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ]
        }

        self.app.create('proid.name', payload)
        app_admin.create.assert_called_with('proid.name', payload)


if __name__ == '__main__':
    unittest.main()
