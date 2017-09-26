"""Instance API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock
import jsonschema

import six

from treadmill import admin
from treadmill import exc
from treadmill import master
from treadmill import yamlwrapper as yaml
from treadmill.api import instance


def _create_apps(_zkclient, _app_id, app, _count, _created_by):
    return app


class ApiInstanceTest(unittest.TestCase):
    """treadmill.api.instance tests."""

    def setUp(self):
        self.instance = instance.API()

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.master.create_apps', mock.Mock())
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    def test_normalize_run_once(self):
        """Test missing defaults which cause the app to fail."""
        doc = """
        services:
        - command: /bin/sleep 1m
          name: sleep1m
          restart:
            limit: 0
        memory: 150M
        cpu: 10%
        disk: 100M
        """

        master.create_apps.side_effect = _create_apps

        new_doc = self.instance.create('proid.app', yaml.load(doc))

        # Disable E1126: Sequence index is not an int, slice, or instance
        # pylint: disable=E1126
        self.assertEqual(new_doc['services'][0]['restart']['interval'], 60)
        self.assertTrue(master.create_apps.called)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.master.create_apps', mock.Mock())
    def test_run_once_small_memory(self):
        """Testing too small memory definition for container."""
        doc = """
        services:
        - command: /bin/sleep 10
          name: sleep1m
          restart:
            limit: 0
        memory: 10M
        cpu: 10%
        disk: 100M
        """

        master.create_apps.side_effect = _create_apps
        with self.assertRaises(exc.TreadmillError):
            self.instance.create('proid.app', yaml.load(doc))

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.admin.Application.get',
                mock.Mock(return_value={
                    '_id': 'proid.app',
                    'tickets': ['foo@bar.baz'],
                    'cpu': '10%',
                    'memory': '100M',
                    'disk': '100M',
                    'endpoints': [{'name': 'http', 'port': 8888}],
                    'services': [{
                        'command': 'python -m SimpleHTTPServer 8888',
                        'name': 'web_server',
                        'restart': {'interval': 60, 'limit': 3}
                    }],
                    'features': [],
                    'ephemeral_ports': {},
                    'passthrough': [],
                    'args': [],
                    'environ': [],
                    'affinity_limits': {}
                }))
    @mock.patch('treadmill.master.create_apps')
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    @mock.patch('treadmill.api.instance._set_defaults',
                mock.Mock())
    def test_instance_create_configured(self, create_apps_mock):
        """Test creating configured instance."""
        create_apps_mock.side_effect = _create_apps

        app = {
            'tickets': ['foo@bar.baz'],
            'cpu': '10%',
            'memory': '100M',
            'disk': '100M',
            'endpoints': [{'name': 'http', 'port': 8888}],
            'services': [{
                'command': 'python -m SimpleHTTPServer 8888',
                'name': 'web_server',
                'restart': {'interval': 60, 'limit': 3}
            }],
            'features': [],
            'ephemeral_ports': {},
            'passthrough': [],
            'args': [],
            'environ': [],
            'affinity_limits': {},
        }

        self.instance.create('proid.app', {})

        create_apps_mock.assert_called_once_with(
            mock.ANY, 'proid.app', app, 1, None
        )

        create_apps_mock.reset_mock()
        self.instance.create('proid.app', {}, created_by='monitor')
        create_apps_mock.assert_called_once_with(
            mock.ANY, 'proid.app', app, 1, 'monitor'
        )

        create_apps_mock.reset_mock()
        self.instance.create('proid.app', {}, 2, 'foo@BAR.BAZ')
        create_apps_mock.assert_called_once_with(
            mock.ANY, 'proid.app', app, 2, 'foo@BAR.BAZ'
        )

        with six.assertRaisesRegex(
            self, jsonschema.exceptions.ValidationError,
            "'invalid!' is not valid"
        ):
            self.instance.create('proid.app', {}, created_by='invalid!')

        with six.assertRaisesRegex(
            self, jsonschema.exceptions.ValidationError,
            "0 is less than the minimum of 1"
        ):
            self.instance.create('proid.app', {}, count=0)

        with six.assertRaisesRegex(
            self, jsonschema.exceptions.ValidationError,
            "1001 is greater than the maximum of 1000"
        ):
            self.instance.create('proid.app', {}, count=1001)

    @mock.patch('treadmill.context.AdminContext.conn',
                mock.Mock(return_value=admin.Admin(None, None)))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.master.delete_apps')
    def test_instance_delete(self, delete_apps_mock):
        """Test deleting an instance."""
        delete_apps_mock.return_value = None

        self.instance.delete('proid.app#0000000001')
        delete_apps_mock.assert_called_once_with(
            mock.ANY, ['proid.app#0000000001'], None
        )

        delete_apps_mock.reset_mock()
        self.instance.delete('proid.app#0000000002', deleted_by='monitor')
        delete_apps_mock.assert_called_once_with(
            mock.ANY, ['proid.app#0000000002'], 'monitor'
        )

        delete_apps_mock.reset_mock()
        self.instance.delete('proid.app#0000000003', deleted_by='foo@BAR.BAZ')
        delete_apps_mock.assert_called_once_with(
            mock.ANY, ['proid.app#0000000003'], 'foo@BAR.BAZ'
        )

        with six.assertRaisesRegex(
            self, jsonschema.exceptions.ValidationError,
            "'invalid!' is not valid"
        ):
            self.instance.delete('proid.app#0000000001', deleted_by='invalid!')


if __name__ == '__main__':
    unittest.main()
