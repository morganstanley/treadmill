"""Unit test for S6 services.
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
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.supervisor import s6
from treadmill.supervisor import _service_base


class ServiceTest(unittest.TestCase):
    """Mock test for treadmill.supervisor.s6.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.supervisor.s6.services.LongrunService',
                mock.Mock(spec_set=True))
    def test_new(self):
        """Test service factory.
        """
        mock_svc = s6.create_service(
            self.root, 'mock', _service_base.ServiceType.LongRun,
            run_script='test'
        )

        self.assertIsNotNone(mock_svc)
        s6.services.LongrunService.assert_called_with(
            self.root, 'mock', run_script='test'
        )

    def test_read_dir(self):
        """Test service reading.
        """
        mock_svc_dir = os.path.join(self.root, 'my_svc')
        os.mkdir(mock_svc_dir)
        with io.open(os.path.join(mock_svc_dir, 'type'), 'w') as f:
            f.write('longrun')

        mock_svc_data = _service_base.Service.read_dir(mock_svc_dir)

        self.assertEqual(
            mock_svc_data,
            (
                _service_base.ServiceType.LongRun,
                self.root,
                'my_svc'
            )
        )

    def test_create_service_read(self):
        """Test parsing of LongRunning service data.
        """
        mock_svc_dir = os.path.join(self.root, 'my_svc')
        os.mkdir(mock_svc_dir)
        with io.open(os.path.join(mock_svc_dir, 'type'), 'w') as f:
            f.write('longrun')
        with io.open(os.path.join(mock_svc_dir, 'run'), 'w') as f:
            f.write('mock run script')
        with io.open(os.path.join(mock_svc_dir, 'down'), 'w') as f:
            pass
        with io.open(os.path.join(mock_svc_dir, 'notification-fd'), 'w') as f:
            f.write('42')
        os.mkdir(os.path.join(mock_svc_dir, 'data'))
        os.mkdir(os.path.join(mock_svc_dir, 'env'))
        with io.open(os.path.join(mock_svc_dir, 'env', 'HOME'), 'w') as f:
            f.write(u'/my/home\n')
        with io.open(os.path.join(mock_svc_dir, 'env', 'FOO'), 'w') as f:
            f.write(u'bar\n')

        mock_svc = s6.create_service(
            self.root,
            'my_svc',
            _service_base.ServiceType.LongRun
        )

        self.assertEqual(mock_svc.type, _service_base.ServiceType.LongRun)
        self.assertEqual(mock_svc.run_script, 'mock run script')
        self.assertEqual(mock_svc.default_down, True)
        self.assertEqual(mock_svc.notification_fd, 42)
        self.assertEqual(
            mock_svc.data_dir,
            os.path.join(self.root, 'my_svc', 'data')
        )
        self.assertEqual(
            mock_svc.env_dir,
            os.path.join(self.root, 'my_svc', 'env')
        )
        self.assertEqual(
            mock_svc.environ,
            {
                'FOO': 'bar',
                'HOME': '/my/home',
            }
        )


if __name__ == '__main__':
    unittest.main()
