"""Unit test for treadmill.appenv
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

from treadmill import appenv


class AppEnvTest(unittest.TestCase):
    """Tests for teadmill.appenv"""

    if sys.platform.startswith('linux'):
        @mock.patch('socket.gethostbyname', mock.Mock(
            return_value='172.31.81.67'
        ))
        @mock.patch('treadmill.services.ResourceService')
        def setUp(self, mock_resource_service):
            # W0221 Arguments number differs from overridden method
            # pylint: disable=W0221
            def _fake_service_factory(impl, *_args, **_kw_args):
                """Generate a unique mock object for each service impl.
                """
                return mock.Mock(name=impl)
            mock_resource_service.side_effect = _fake_service_factory
            self.root = tempfile.mkdtemp()
            self.tm_env = appenv.AppEnvironment(root=self.root)
    else:
        def setUp(self):
            self.root = tempfile.mkdtemp()
            self.tm_env = appenv.AppEnvironment(root=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.iptables.initialize', mock.Mock())
    @mock.patch('treadmill.rulefile.RuleMgr.initialize', mock.Mock())
    @mock.patch('treadmill.runtime.linux.image.fs.init_plugins', mock.Mock())
    def test_initialize_linux(self):
        """Test AppEnv environment initialization.
        """
        self.tm_env.initialize({
            'node': 'data',
            'network': {
                'external_ip': 'foo',
            }
        })

        self.tm_env.rules.initialize.assert_called_with()
        # TODO: Renable iptables init in linux AppEnv initialize
        # treadmill.iptables.initialize.assert_called_with('foo')

        self.assertTrue(hasattr(self.tm_env, 'alerts_dir'))


if __name__ == '__main__':
    unittest.main()
