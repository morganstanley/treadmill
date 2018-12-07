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

from treadmill import exc
from treadmill import yamlwrapper as yaml
from treadmill.api import instance
from treadmill.scheduler import masterapi
from treadmill.admin import ldapbackend


def _create_apps(_zkclient, _app_id, app, _count, _created_by):
    return app


class ApiInstanceTest(unittest.TestCase):
    """treadmill.api.instance tests."""

    def setUp(self):
        self.instance = instance.API()

    @mock.patch('treadmill.context.AdminContext._conn',
                ldapbackend.AdminLdapBackend('', ''))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_apps', mock.Mock())
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
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
        traits:
        - foo
        """

        masterapi.create_apps.side_effect = _create_apps

        new_doc = self.instance.create('proid.app', yaml.load(doc))

        # Disable E1126: Sequence index is not an int, slice, or instance
        # pylint: disable=E1126
        self.assertEqual(new_doc['services'][0]['restart']['interval'], 60)
        self.assertTrue(masterapi.create_apps.called)

    @mock.patch('treadmill.context.AdminContext._conn',
                ldapbackend.AdminLdapBackend('', ''))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_apps', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
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

        masterapi.create_apps.side_effect = _create_apps
        with self.assertRaises(exc.TreadmillError):
            self.instance.create('proid.app', yaml.load(doc))

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.context.AdminContext.application',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {
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
                    }
                })))
    @mock.patch('treadmill.scheduler.masterapi.create_apps')
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    @mock.patch('treadmill.api.instance._set_defaults',
                mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
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

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   'u?\'invalid!\' is not valid'):
            self.instance.create('proid.app', {}, created_by='invalid!')

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '0 is less than the minimum of 1'):
            self.instance.create('proid.app', {}, count=0)

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '1001 is greater than the maximum of 1000'):
            self.instance.create('proid.app', {}, count=1001)

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.delete_apps')
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

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   'u?\'invalid!\' is not valid'):
            self.instance.delete('proid.app#0000000001', deleted_by='invalid!')

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.context.AdminContext.application',
                mock.Mock(return_value=mock.Mock(**{
                    'get.return_value': {
                        '_id': 'proid.app',
                        'cpu': '10%',
                        'memory': '100M',
                        'disk': '100M',
                        'image': 'docker://foo',
                    }
                })))
    @mock.patch('treadmill.scheduler.masterapi.create_apps')
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    @mock.patch('treadmill.api.instance._set_defaults', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
    def test_inst_create_cfg_docker(self, create_apps_mock):
        """Test creating configured docker instance.
        """
        create_apps_mock.side_effect = _create_apps

        app = {
            'cpu': '10%',
            'memory': '100M',
            'disk': '100M',
            'image': 'docker://foo',
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

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   'u?\'invalid!\' is not valid'):
            self.instance.create('proid.app', {}, created_by='invalid!')

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '0 is less than the minimum of 1'):
            self.instance.create('proid.app', {}, count=0)

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '1001 is greater than the maximum of 1000'):
            self.instance.create('proid.app', {}, count=1001)

    @mock.patch('treadmill.context.AdminContext._conn',
                ldapbackend.AdminLdapBackend('', ''))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_apps')
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    @mock.patch('treadmill.api.instance._set_defaults',
                mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
    def test_inst_create_eph_docker(self, create_apps_mock):
        """Test creating ephemeral docker instance.
        """
        create_apps_mock.side_effect = _create_apps

        ephemeral_app = {
            'cpu': '10%',
            'memory': '100M',
            'disk': '100M',
            'image': 'docker://foo',
        }
        resulting_app = {
            'cpu': '10%',
            'memory': '100M',
            'disk': '100M',
            'image': 'docker://foo',
            'tickets': [],
            'endpoints': [],
            'features': [],
            'ephemeral_ports': {},
            'passthrough': [],
            'args': [],
            'environ': [],
            'affinity_limits': {},
            'traits': [],
        }

        self.instance.create('proid.app', ephemeral_app)
        create_apps_mock.assert_called_once_with(
            mock.ANY, 'proid.app', resulting_app, 1, None
        )

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   'u?\'invalid!\' is not valid'):
            self.instance.create('proid.app', {}, created_by='invalid!')

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '0 is less than the minimum of 1'):
            self.instance.create('proid.app', {}, count=0)

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '1001 is greater than the maximum of 1000'):
            self.instance.create('proid.app', {}, count=1001)

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.delete_apps')
    def test_instance_bulk_delete(self, delete_apps_mock):
        """Test bulk deleting
        """
        delete_apps_mock.return_value = None

        self.instance.bulk_delete(
            'proid',
            ['proid.app#0000000001', 'proid.app#0000000002']
        )
        delete_apps_mock.assert_called_once_with(
            mock.ANY, ['proid.app#0000000001', 'proid.app#0000000002'], None
        )

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.update_app_priorities')
    def test_instance_bulk_update(self, update_apps_mock):
        """Test bulk updateing
        """
        update_apps_mock.return_value = None

        self.instance.bulk_update(
            'proid',
            [{'_id': 'proid.app#0000000001', 'priority': 1}]
        )
        update_apps_mock.assert_called_with(
            mock.ANY, {'proid.app#0000000001': 1}
        )

    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_apps', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats')
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    def test_quotas(self, scheduled_stats_mock):
        """Test quotas enforcement.
        """
        doc = """
        services:
        - command: /bin/sleep 10
          name: sleep1m
          restart:
            limit: 0
        memory: 100M
        cpu: 10%
        disk: 100M
        """

        scheduled_stats_mock.return_value = {'xxx': 50000}
        with self.assertRaises(exc.QuotaExceededError):
            self.instance.create('yyy.app', yaml.load(doc), count=1)

        scheduled_stats_mock.return_value = {'xxx': 49900}
        with self.assertRaises(exc.QuotaExceededError):
            self.instance.create('yyy.app', yaml.load(doc), count=101)

        scheduled_stats_mock.return_value = {'yyy': 10000}
        with self.assertRaises(exc.QuotaExceededError):
            self.instance.create('yyy.app', yaml.load(doc), count=1)

        scheduled_stats_mock.return_value = {'yyy': 9900}
        with self.assertRaises(exc.QuotaExceededError):
            self.instance.create('yyy.app', yaml.load(doc), count=101)

    @mock.patch('treadmill.context.AdminContext._conn',
                ldapbackend.AdminLdapBackend('', ''))
    @mock.patch('treadmill.context.ZkContext.conn', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_apps')
    @mock.patch('treadmill.scheduler.masterapi.get_scheduled_stats',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.api.instance._check_required_attributes',
                mock.Mock())
    def test_debug_services(self, create_apps_mock):
        """Test debugging services.
        """
        doc = """
        services:
        - command: /bin/sleep 10
          name: sleep1
          restart:
            limit: 0
        - command: /bin/sleep 10
          name: sleep2
          restart:
            limit: 0
        - command: /bin/sleep 10
          name: sleep3
          restart:
            limit: 0
        memory: 100M
        cpu: 10%
        disk: 100M
        """

        # Don't debug services (no debug/debug_services).
        self.instance.create('proid.app', yaml.load(doc))

        create_apps_mock.assert_called_once()
        args, _kwargs = create_apps_mock.call_args
        _zkclient, _app_id, app, _count, _created_by = args
        self.assertEqual(
            [svc['name'] for svc in app['services'] if svc.get('downed')],
            []
        )

        create_apps_mock.reset_mock()

        # Debug all services (debug without debug_services).
        self.instance.create('proid.app', yaml.load(doc), debug=True)

        create_apps_mock.assert_called_once()
        args, _kwargs = create_apps_mock.call_args
        _zkclient, _app_id, app, _count, _created_by = args
        self.assertEqual(
            [svc['name'] for svc in app['services'] if svc.get('downed')],
            ['sleep1', 'sleep2', 'sleep3']
        )

        create_apps_mock.reset_mock()

        # Debug selected services (debug_services with a list of services).
        self.instance.create(
            'proid.app', yaml.load(doc), debug_services=['sleep1', 'sleep2']
        )

        create_apps_mock.assert_called_once()
        args, _kwargs = create_apps_mock.call_args
        _zkclient, _app_id, app, _count, _created_by = args
        self.assertEqual(
            [svc['name'] for svc in app['services'] if svc.get('downed')],
            ['sleep1', 'sleep2']
        )


if __name__ == '__main__':
    unittest.main()
