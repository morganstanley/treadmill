"""Cell API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock
from jsonschema import exceptions as jexceptions

import treadmill
from treadmill.api import app


class ApiAppTest(unittest.TestCase):
    """treadmill.api.app tests."""

    def setUp(self):
        self.app = app.API()

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.AdminContext.application')
    def test_list(self, app_factory):
        """Test treadmill.api.app._list()"""
        apps = [
            {
                '_id': 'foo.app1',
                'affinity_limits': {},
                'args': [],
                'cpu': '100%',
                'disk': '1G',
                'endpoints': [],
                'environ': [],
                'ephemeral_ports': {},
                'features': [],
                'memory': '1G',
                'passthrough': [],
                'services': [],
                'tickets': [],
                'traits': [],
            },
            {
                '_id': 'foo.app2',
                'affinity_limits': {},
                'args': [],
                'cpu': '100%',
                'disk': '1G',
                'endpoints': [],
                'environ': [],
                'ephemeral_ports': {},
                'features': [],
                'memory': '1G',
                'passthrough': [],
                'services': [],
                'tickets': [],
                'traits': [],
            },
            {
                '_id': 'bar.app1',
                'affinity_limits': {},
                'args': [],
                'cpu': '100%',
                'disk': '1G',
                'endpoints': [],
                'environ': [],
                'ephemeral_ports': {},
                'features': [],
                'memory': '1G',
                'passthrough': [],
                'services': [],
                'tickets': [],
                'traits': [],
            },
        ]
        # paged_search returns generator
        admin_mock = app_factory.return_value
        admin_mock.list.return_value = apps

        self.assertEqual(
            self.app.list(match='foo.*'),
            [
                {
                    '_id': 'foo.app1',
                    'affinity_limits': {},
                    'args': [],
                    'cpu': '100%',
                    'disk': '1G',
                    'endpoints': [],
                    'environ': [],
                    'ephemeral_ports': {},
                    'features': [],
                    'memory': '1G',
                    'passthrough': [],
                    'services': [],
                    'tickets': [],
                    'traits': [],
                },
                {
                    '_id': 'foo.app2',
                    'affinity_limits': {},
                    'args': [],
                    'cpu': '100%',
                    'disk': '1G',
                    'endpoints': [],
                    'environ': [],
                    'ephemeral_ports': {},
                    'features': [],
                    'memory': '1G',
                    'passthrough': [],
                    'services': [],
                    'tickets': [],
                    'traits': [],
                },
            ]
        )

    @mock.patch('treadmill.context.AdminContext.application')
    def test_list_proid_filtering(self, app_factory):
        """Test treadmill.api.app._list() proid filtering"""
        apps = [
            {'_id': 'foo.app1'},
            {'_id': 'foo.app2'},
            {'_id': 'bar.app1'},
        ]
        admin_mock = app_factory.return_value
        admin_mock.list.return_value = apps

        result = self.app.list()
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2', 'bar.app1'}
        )

        result = self.app.list(match='*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2', 'bar.app1'}
        )

        result = self.app.list(match='foo.*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )

        result = self.app.list(match='foo.app?')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )

        result = self.app.list(match='foo?app*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )

    @mock.patch('treadmill.context.AdminContext.application',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {}
                })))
    def test_get(self):
        """Dummy test for treadmill.api.cell.get()"""
        app_admin = treadmill.context.AdminContext.application.return_value
        self.app.get('proid.name')
        app_admin.get.assert_called_with('proid.name')

    @mock.patch('treadmill.context.AdminContext.application')
    def test_create(self, app_admin):
        """Dummy test for treadmill.api.cell.create().
        """
        app_admin.return_value = mock.Mock(**{
            'get.return_value': {},
        })
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
        app_admin.return_value.create.assert_called_with('proid.name', payload)

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

    @mock.patch('treadmill.context.AdminContext.application')
    def test_create_valid_affinity(self, app_factory):
        """Test valid affinity name for treadmill.api.cell.create().
        """
        app_admin = app_factory.return_value
        app_admin.get.return_value = {}
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

    @mock.patch('treadmill.context.AdminContext.application')
    def test_create_docker(self, app_factory):
        """Dummy test for treadmill.api.cell.create() for docker"""
        app_admin = app_factory.return_value
        app_admin.get.return_value = {}
        payload = {
            'cpu': '100%',
            'memory': '1G',
            'disk': '20G',
            'image': 'docker://microsoft/windowsservercore',
            'endpoints': [
                {'name': 'x', 'port': 1, 'type': 'infra'},
                {'name': 'y', 'port': 2, 'type': 'infra'},
            ],
            'services': [
                {
                    'name': 'foo',
                    'image': 'testimage',
                    'useshell': True,
                    'command': 'echo',
                    'restart': {
                        'limit': 3,
                        'interval': 30,
                    },
                },
                {
                    'name': 'bar',
                    'image': 'testimage',
                    'useshell': False,
                    'command': 'echo',
                    'restart': {
                        'limit': 3,
                        'interval': 30,
                    },
                },
            ],
        }

        self.app.create('proid.name', payload)
        app_admin.create.assert_called_with('proid.name', payload)

    @mock.patch('treadmill.context.AdminContext.application')
    def test_create_result(self, app_factory):
        """Test response for treadmill.api.app.create().
        """
        admin_mock = app_factory.return_value
        entry = {
            'cpu': '100%',
            'disk': '1G',
            'memory': '1G',
            'services': [{'name': 'test_svc', 'command': 'test_cmd'}],
        }
        admin_mock.get.return_value = entry

        result = self.app.create(
            'foo.app',
            entry
        )

        admin_mock.create.assert_called_once_with(
            'foo.app',
            entry
        )

        self.assertEqual(
            result, entry
        )

    @mock.patch('treadmill.context.AdminContext.application')
    def test_update_result(self, app_factory):
        """Test response for treadmill.api.app.update().
        """
        admin_mock = app_factory.return_value
        payload = {
            'cpu': '100%',
            'disk': '1G',
            'memory': '1G',
            'services': [{'name': 'test_svc', 'command': 'test_cmd'}],
        }

        self.app.update('foo.app', payload)
        admin_mock.replace.assert_called_once_with('foo.app', payload)


if __name__ == '__main__':
    unittest.main()
