"""Unit test for treadmill.appcfg.configure.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

import mock

import treadmill
import treadmill.services

from treadmill.appcfg import configure as app_cfg
from treadmill.apptrace import events


class AppCfgConfigureTest(unittest.TestCase):
    """Tests for teadmill.appcfg.configure"""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.tm_env = mock.Mock(
            apps_dir=os.path.join(self.root, 'apps'),
            cleanup_dir=os.path.join(self.root, 'cleanup'),
            svc_cgroup=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_localdisk=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_network=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    @mock.patch('shutil.copyfile', mock.Mock(auto_spec=True))
    @mock.patch('treadmill.appcfg.manifest.load', auto_spec=True)
    @mock.patch('treadmill.appevents.post', mock.Mock(auto_spec=True))
    @mock.patch('treadmill.fs.write_safe', mock.mock_open())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    @mock.patch('treadmill.supervisor.create_service', auto_spec=True)
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_configure(self, mock_create_svc, mock_load):
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

        mock_load.assert_called_with(self.tm_env, '/some/event', 'linux')
        mock_create_svc.assert_called_with(
            self.tm_env.apps_dir,
            name=app_unique_name,
            app_run_script=mock.ANY,
            downed=True,
            monitor_policy={'limit': 0, 'interval': 60},
            userid='root',
            environ={},
            environment='dev'
        )
        treadmill.fs.write_safe.assert_called_with(
            os.path.join(app_dir, 'data', 'app.json'),
            mock.ANY,
            permission=0o644
        )

        shutil.copyfile.assert_called_with(
            '/some/event',
            os.path.join(app_dir, 'data', 'manifest.yml')
        )

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.ConfiguredTraceEvent(
                instanceid='proid.myapp#0',
                uniqueid='AAAAA',
                payload=None
            )
        )


if __name__ == '__main__':
    unittest.main()
