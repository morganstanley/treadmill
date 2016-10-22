"""
Unit test for treadmill.appmgr.manifest
"""

import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

import treadmill
from treadmill.appmgr import manifest as app_manifest
from treadmill import context


class AppMgrManifestTest(unittest.TestCase):
    """Tests for teadmill.appmgr."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        context.GLOBAL.cell = 'testcell'
        context.GLOBAL.zk.url = 'zookeeper://foo@foo:123'
        self.app_env = mock.Mock(
            cell='testcell',
            host_ip='1.2.3.4',
            zkurl='zookeeper://foo@foo:123',
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.appmgr.gen_uniqueid', mock.Mock(return_value='42'))
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_load(self):
        """Tests loading app manifest with resource allocation."""
        manifest = {
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/sleep 5',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    }
                }
            ],
            'proid': 'foo',
            'disk': '100G',
            'cpu': '100%',
            'memory': '100M'
        }

        treadmill.subproc.EXECUTABLES = {
            'sshd': '/path/to/sshd',
        }

        treadmill.appmgr.manifest.read.return_value = manifest
        event_filename0 = os.path.join(self.root, 'proid.myapp#0')

        app0 = app_manifest.load(self.app_env, event_filename0)

        treadmill.appmgr.manifest.read.assert_called_with(event_filename0)
        treadmill.appmgr.gen_uniqueid.assert_called_with(event_filename0)
        self.assertEquals(app0['name'], 'proid.myapp#0')
        self.assertEquals(app0['app'], 'proid.myapp')
        self.assertEquals(app0['proid'], 'foo')
        self.assertEquals(app0['environment'], 'dev')
        self.assertEquals(app0['cpu'], 100)
        self.assertEquals(app0['memory'], '100M')
        self.assertEquals(app0['disk'], '100G')
        self.assertEquals(
            app0['services'],
            [
                {
                    'name': 'web_server',
                    'command': '/bin/sleep 5',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ]
        )
        self.assertEquals(
            app0['system_services'],
            [
                {
                    'command': (
                        '/path/to/sshd'
                        ' -D -f /etc/ssh/sshd_config'
                        ' -p $TREADMILL_ENDPOINT_SSH'
                    ),
                    'name': 'sshd',
                    'proid': None,
                    'restart': {
                        'limit': 5,
                        'interval': 60,
                    },
                }
            ]
        )
        self.assertEquals(app0['shared_ip'], False)
        self.assertEquals(app0['shared_network'], False)
        self.assertEquals(
            app0['endpoints'], [{'name': 'ssh', 'type': 'infra', 'port': 0}]
        )
        self.assertEquals(app0['ephemeral_ports'], 0)
        self.assertEquals(app0['passthrough'], [])
        self.assertEquals(app0['uniqueid'], '42')
        self.assertEquals(app0['host_ip'], '1.2.3.4')
        self.assertEquals(app0['cell'], 'testcell')
        self.assertEquals(app0['zookeeper'], 'zookeeper://foo@foo:123')
        self.assertEquals(app0['vring']['cells'], [])
        self.assertEquals(app0['identity'], None)
        self.assertEquals(app0['identity_group'], None)

    def test__add_features(self):
        """Tests optional container features."""
        # Access protected member _add_features
        # pylint: disable=W0212
        manifest = {
            'services': [],
            'system_services': [],
            'features': ['webauthd']
        }

        treadmill.appmgr.manifest._add_features(manifest)

        self.assertIn(
            {
                'name': 'webauthd',
                'proid': None,
                'command': '${TREADMILL}/sbin/run_webauthd',
                'restart': {
                    'limit': 5,
                    'interval': 60,
                },
            },
            manifest['system_services']
        )

    def test__add_features_nonexist(self):
        """Tests adding non-existant container features."""
        # Access protected member _add_features
        # pylint: disable=W0212
        manifest = {
            'services': [],
            'system_services': [],
            'features': ['webauthd', 'no_such_feature']
        }

        self.assertRaises(
            Exception,
            treadmill.appmgr.manifest._add_features,
            manifest
        )


if __name__ == '__main__':
    unittest.main()
