"""Unit test for treadmill.runtime.linux.runtime.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

from treadmill import exc
from treadmill import services
from treadmill import utils

from treadmill.appcfg import abort as app_abort
from treadmill.runtime.linux import runtime


class LinuxRuntimeTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux.runtime.LinuxRuntime."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

        self.tm_env = mock.Mock(
            configs_dir=os.path.join(self.root, 'confs')
        )
        self.container_dir = os.path.join(self.root, 'apps', 'foo.bar-0-baz')

        self.data_dir = os.path.join(self.container_dir, 'data')
        os.makedirs(self.data_dir)

        patch = mock.patch(
            'treadmill.supervisor.open_service',
            return_value=mock.Mock(
                data_dir=self.data_dir
            )
        )
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.runtime.linux.runtime._load_config', mock.Mock())
    def test_run_invalid_type(self):
        """Test run aborting with invalid type."""
        with io.open(os.path.join(self.data_dir, 'app.json'), 'w') as f:
            f.writelines(utils.json_genencode({'type': 'invalid'}, indent=4))

        with self.assertRaises(exc.ContainerSetupError) as cm:
            runtime.LinuxRuntime(self.tm_env, self.container_dir).run()

        self.assertEqual(
            cm.exception.reason, app_abort.AbortedReason.INVALID_TYPE
        )

    @mock.patch('treadmill.runtime.linux.runtime._load_config', mock.Mock())
    @mock.patch(
        'treadmill.runtime.linux._run.run',
        side_effect=services.ResourceServiceTimeoutError(
            'Resource not available in time'
        )
    )
    def test_run_timeout(self, _mock_run):
        """Test run aborting with timeout."""
        with io.open(os.path.join(self.data_dir, 'app.json'), 'w') as f:
            f.writelines(utils.json_genencode({'type': 'native'}, indent=4))
        with self.assertRaises(exc.ContainerSetupError) as cm:
            runtime.LinuxRuntime(self.tm_env, self.container_dir).run()

        self.assertEqual(
            cm.exception.reason, app_abort.AbortedReason.TIMEOUT
        )


if __name__ == '__main__':
    unittest.main()
