"""Cell API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

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

    @mock.patch('treadmill.context.AdminContext.conn')
    def test_list(self, admin_mock):
        """Test treadmill.api.app._list()"""
        apps = [
            (
                'app=foo.app1,ou=apps,ou=treadmill,dc=ms,dc=com',
                {
                    'app': ['foo.app1'],
                    'memory': ['1G'],
                    'cpu': ['100%'],
                    'disk': ['1G'],
                }
            ),
            (
                'app=foo.app2,ou=apps,ou=treadmill,dc=ms,dc=com',
                {
                    'app': ['foo.app2'],
                    'memory': ['1G'],
                    'cpu': ['100%'],
                    'disk': ['1G'],
                }
            ),
            (
                'app=bar.app1,ou=apps,ou=treadmill,dc=ms,dc=com',
                {
                    'app': ['bar.app1'],
                    'memory': ['1G'],
                    'cpu': ['100%'],
                    'disk': ['1G'],
                }
            ),
        ]
        # paged_search returns generator
        admin_mock.paged_search.return_value = (
            (dn, entry) for dn, entry in apps
        )

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
                },
            ]
        )

    @mock.patch('treadmill.context.AdminContext.conn')
    def test_list_proid_filtering(self, admin_mock):
        """Test treadmill.api.app._list() proid filtering"""
        apps = [
            (
                'app=foo.app1,ou=apps,ou=treadmill,dc=ms,dc=com',
                {'app': ['foo.app1']}
            ),
            (
                'app=foo.app2,ou=apps,ou=treadmill,dc=ms,dc=com',
                {'app': ['foo.app2']}
            ),
            (
                'app=bar.app1,ou=apps,ou=treadmill,dc=ms,dc=com',
                {'app': ['bar.app1']}
            ),
        ]
        admin_mock.paged_search.return_value = apps

        result = self.app.list()
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2', 'bar.app1'}
        )
        _args, kwargs = admin_mock.paged_search.call_args
        self.assertEqual(
            kwargs['search_filter'],
            '(objectClass=tmApp)'
        )

        result = self.app.list(match='*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2', 'bar.app1'}
        )
        _args, kwargs = admin_mock.paged_search.call_args
        self.assertEqual(
            kwargs['search_filter'],
            '(objectClass=tmApp)'
        )

        result = self.app.list(match='foo.*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )
        _args, kwargs = admin_mock.paged_search.call_args
        self.assertEqual(
            kwargs['search_filter'],
            '(&(objectClass=tmApp)(app=foo.*))'
        )

        result = self.app.list(match='foo.app?')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )
        _args, kwargs = admin_mock.paged_search.call_args
        self.assertEqual(
            kwargs['search_filter'],
            '(&(objectClass=tmApp)(app=foo.*))'
        )

        result = self.app.list(match='foo?app*')
        self.assertEqual(
            {item['_id'] for item in result},
            {'foo.app1', 'foo.app2'}
        )
        _args, kwargs = admin_mock.paged_search.call_args
        self.assertEqual(
            kwargs['search_filter'],
            '(objectClass=tmApp)'
        )

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

    @mock.patch('treadmill.context.AdminContext.conn')
    def test_create_result(self, admin_mock):
        """Test response for treadmill.api.app.create().
        """
        admin_mock.dn.return_value = (
            'app=app.foo,ou=apps,ou=treadmill,dc=ms,dc=com'
        )
        checksum = '6bf2b2db162e3043738a5c1d4e62bef5'
        entry = {
            'app': ['foo.app'],
            'cpu': ['100%'],
            'disk': ['1G'],
            'memory': ['1G'],
            'service-name;tm-service-%s' % checksum: ['test_svc'],
            'service-command;tm-service-%s' % checksum: ['test_cmd'],
            'service-restart-limit;tm-service-%s' % checksum: ['5'],
            'service-restart-interval;tm-service-%s' % checksum: ['60'],
        }
        admin_mock.get.return_value = entry

        result = self.app.create(
            'foo.app',
            {
                'cpu': '100%',
                'disk': '1G',
                'memory': '1G',
                'services': [{'name': 'test_svc', 'command': 'test_cmd'}],
            }
        )

        entry.update({'objectClass': ['tmApp']})
        admin_mock.create.assert_called_once_with(
            'app=app.foo,ou=apps,ou=treadmill,dc=ms,dc=com',
            entry
        )

        self.assertEqual(
            result,
            {
                '_id': 'foo.app',
                'cpu': '100%',
                'disk': '1G',
                'memory': '1G',
                'services': [{
                    'name': 'test_svc',
                    'command': 'test_cmd',
                    'restart': {'limit': 5, 'interval': 60},
                }],
                'args': [],
                'endpoints': [],
                'environ': [],
                'features': [],
                'passthrough': [],
                'tickets': [],
                'ephemeral_ports': {},
                'affinity_limits': {},
            }
        )

    @mock.patch('treadmill.context.AdminContext.conn')
    def test_update_result(self, admin_mock):
        """Test response for treadmill.api.app.update().
        """
        admin_mock.dn.return_value = (
            'app=app.foo,ou=apps,ou=treadmill,dc=ms,dc=com'
        )
        checksum = '6bf2b2db162e3043738a5c1d4e62bef5'
        entry = {
            'app': ['foo.app'],
            'cpu': ['100%'],
            'disk': ['1G'],
            'memory': ['1G'],
            'service-name;tm-service-%s' % checksum: ['test_svc'],
            'service-command;tm-service-%s' % checksum: ['test_cmd'],
            'service-restart-limit;tm-service-%s' % checksum: ['5'],
            'service-restart-interval;tm-service-%s' % checksum: ['60'],
        }
        admin_mock.get.return_value = entry

        result = self.app.update(
            'foo.app',
            {
                'cpu': '100%',
                'disk': '1G',
                'memory': '1G',
                'services': [{'name': 'test_svc', 'command': 'test_cmd'}],
            }
        )

        admin_mock.delete.assert_called_once_with(
            'app=app.foo,ou=apps,ou=treadmill,dc=ms,dc=com'
        )
        entry.update({'objectClass': ['tmApp']})
        admin_mock.create.assert_called_once_with(
            'app=app.foo,ou=apps,ou=treadmill,dc=ms,dc=com',
            entry
        )

        self.assertEqual(
            result,
            {
                '_id': 'foo.app',
                'cpu': '100%',
                'disk': '1G',
                'memory': '1G',
                'services': [{
                    'name': 'test_svc',
                    'command': 'test_cmd',
                    'restart': {'limit': 5, 'interval': 60},
                }],
                'args': [],
                'endpoints': [],
                'environ': [],
                'features': [],
                'passthrough': [],
                'tickets': [],
                'ephemeral_ports': {},
                'affinity_limits': {},
            }
        )


if __name__ == '__main__':
    unittest.main()
