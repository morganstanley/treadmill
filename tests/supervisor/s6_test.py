"""
Unit test for S6 services
"""

import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

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
        with open(os.path.join(mock_svc_dir, 'type'), 'a') as f:
            f.write('longrun')
        with open(os.path.join(mock_svc_dir, 'run'), 'a') as f:
            f.write('mock run script')
        with open(os.path.join(mock_svc_dir, 'down'), 'a') as f:
            pass
        with open(os.path.join(mock_svc_dir, 'notification-fd'), 'a') as f:
            f.write('42')
        os.mkdir(os.path.join(mock_svc_dir, 'data'))
        os.mkdir(os.path.join(mock_svc_dir, 'env'))
        with open(os.path.join(mock_svc_dir, 'env', 'HOME'), 'a') as f:
            f.write('/my/home\n')
        with open(os.path.join(mock_svc_dir, 'env', 'FOO'), 'a') as f:
            f.write('bar\n')

        mock_svc = _service_base.Service.read_dir(mock_svc_dir,
                                                  s6.create_service)

        self.assertIsNotNone(mock_svc)
        self.assertEqual(
            mock_svc.directory,
            os.path.join(self.root, 'my_svc')
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
