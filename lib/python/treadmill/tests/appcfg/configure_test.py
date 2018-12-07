"""Unit test for treadmill.appcfg.configure.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import sys
import tempfile
import unittest

import mock

import treadmill

from treadmill.appcfg import configure as app_cfg
from treadmill.trace.app import events


class AppCfgConfigureTest(unittest.TestCase):
    """Tests for teadmill.appcfg.configure"""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.tm_env = mock.Mock(
            apps_dir=os.path.join(self.root, 'apps'),
            cleanup_dir=os.path.join(self.root, 'cleanup'),
            running_tombstone_dir=os.path.join(self.root, 'tombstones',
                                               'running')
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    @mock.patch('shutil.copyfile', mock.Mock(auto_spec=True))
    @mock.patch('treadmill.appcfg.manifest.load', auto_spec=True)
    @mock.patch('treadmill.trace.post', mock.Mock(auto_spec=True))
    @mock.patch('treadmill.fs.write_safe', mock.mock_open())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='mock'))
    @mock.patch('treadmill.supervisor.create_service', auto_spec=True)
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_configure_linux(self, mock_create_svc, mock_load):
        """Tests that appcfg.configure creates necessary s6 layout."""
        manifest = {
            'proid': 'foo',
            'environment': 'dev',
            'shared_network': False,
            'cpu': '100',
            'memory': '100M',
            'disk': '100G',
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/true',
                    'restart': {
                        'limit': 5,
                        'interval': 60,
                    },
                },
            ],
            'environ': [
                {
                    'name': 'Hello',
                    'value': 'World!',
                },
            ],
            'zookeeper': 'foo',
            'cell': 'cell',
            'system_services': [],
            'endpoints': [
                {
                    'name': 'http',
                    'port': '8000',
                },
            ],
            'name': 'proid.myapp#0',
            'uniqueid': 'AAAAA',
        }
        mock_load.return_value = manifest
        app_unique_name = 'proid.myapp-0-00000000AAAAA'
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        mock_create_svc.return_value.data_dir = os.path.join(app_dir, 'data')

        app_cfg.configure(self.tm_env, '/some/event', 'linux')

        mock_load.assert_called_with('/some/event')
        mock_create_svc.assert_called_with(
            self.tm_env.apps_dir,
            name=app_unique_name,
            app_run_script=mock.ANY,
            downed=False,
            monitor_policy={
                'limit': 0,
                'interval': 60,
                'tombstone': {
                    'uds': False,
                    'path': self.tm_env.running_tombstone_dir,
                    'id': 'proid.myapp#0'
                }
            },
            userid='root',
            environ={},
            environment='dev'
        )
        treadmill.fs.write_safe.assert_called_with(
            os.path.join(app_dir, 'data', 'app.json'),
            mock.ANY,
            mode='w',
            permission=0o644
        )

        shutil.copyfile.assert_called_with(
            '/some/event',
            os.path.join(app_dir, 'data', 'manifest.yml')
        )

        treadmill.trace.post.assert_called_with(
            mock.ANY,
            events.ConfiguredTraceEvent(
                instanceid='proid.myapp#0',
                uniqueid='AAAAA',
                payload=None
            )
        )

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    @mock.patch('shutil.copyfile', mock.Mock(auto_spec=True))
    @mock.patch('shutil.rmtree', mock.Mock())
    @mock.patch('treadmill.appcfg.manifest.load', auto_spec=True)
    @mock.patch('treadmill.trace.post', mock.Mock(auto_spec=True))
    @mock.patch('treadmill.fs.write_safe', mock.mock_open())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='mock'))
    @mock.patch('treadmill.supervisor.create_service', auto_spec=True)
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_configure_linux_event_rm(self, mock_create_svc, mock_load):
        """Tests when event file is removed when copied."""
        manifest = {
            'proid': 'foo',
            'environment': 'dev',
            'shared_network': False,
            'cpu': '100',
            'memory': '100M',
            'disk': '100G',
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/true',
                    'restart': {
                        'limit': 5,
                        'interval': 60,
                    },
                },
            ],
            'system_services': [],
            'endpoints': [
                {
                    'name': 'http',
                    'port': '8000',
                },
            ],
            'environ': [
                {
                    'name': 'Hello',
                    'value': 'World!',
                },
            ],
            'cell': 'cell',
            'zookeeper': 'foo',
            'name': 'proid.myapp#0',
            'uniqueid': 'AAAAA',
        }
        mock_load.return_value = manifest
        app_unique_name = 'proid.myapp-0-00000000AAAAA'
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        mock_create_svc.return_value.directory = app_dir
        mock_create_svc.return_value.data_dir = os.path.join(app_dir, 'data')

        shutil.copyfile.side_effect = IOError(2, 'No such file or directory')

        app_cfg.configure(self.tm_env, '/some/event', 'linux')

        mock_load.assert_called_with('/some/event')
        mock_create_svc.assert_called_with(
            self.tm_env.apps_dir,
            name=app_unique_name,
            app_run_script=mock.ANY,
            downed=False,
            monitor_policy={
                'limit': 0,
                'interval': 60,
                'tombstone': {
                    'uds': False,
                    'path': self.tm_env.running_tombstone_dir,
                    'id': 'proid.myapp#0'
                }
            },
            userid='root',
            environ={},
            environment='dev'
        )

        shutil.copyfile.assert_called_with(
            '/some/event',
            os.path.join(app_dir, 'data', 'manifest.yml')
        )

        treadmill.fs.write_safe.assert_not_called()
        shutil.rmtree.assert_called_with(app_dir)

        treadmill.trace.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
