"""Unit test for treadmill.appenv
"""

import os
import shutil
import tempfile
import unittest

import mock

import treadmill
from treadmill import appenv


class AppEnvTest(unittest.TestCase):
    """Tests for teadmill.appenv"""

    @mock.patch('socket.gethostbyname', mock.Mock(
        return_value='172.31.81.67'
    ))
    @mock.patch('treadmill.services.ResourceService')
    def setUp(self, mock_resource_service):
        # W0221 Arguments number differs from overridden method
        # pylint: disable=W0221
        def _fake_service_factory(impl, *_args, **_kw_args):
            """Generate a unique mock object for each service implementation.
            """
            return mock.Mock(name=impl)
        mock_resource_service.side_effect = _fake_service_factory
        self.root = tempfile.mkdtemp()
        self.tm_env = appenv.AppEnvironment(root=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('os.kill', mock.Mock())
    @mock.patch('treadmill.iptables.initialize', mock.Mock())
    @mock.patch('treadmill.sysinfo.port_range',
                mock.Mock(return_value=(5050, 65535)))
    def test_initialize(self):
        """Test AppEnv environment initialization.
        """
        self.tm_env.initialize()
        self.assertFalse(os.kill.called)
        treadmill.iptables.initialize.assert_called_with('172.31.81.67')


if __name__ == '__main__':
    unittest.main()
