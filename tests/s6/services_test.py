"""Unit test for S6 services
"""

import os
import shutil
import tempfile
import unittest

import mock

from treadmill.s6 import services


class ServiceTest(unittest.TestCase):
    """Mock test for treadmill.s6.services.Service.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.s6.services.LongrunService',
                mock.Mock(spec_set=True))
    def test_new(self):
        """Test service factory.
        """
        mock_svc = services.Service.new(
            self.root, 'mock', services.ServiceType.LongRun,
            foo=1, bar=2, baz=3
        )

        self.assertIsNotNone(mock_svc)
        services.LongrunService.assert_called_with(
            directory=self.root, name='mock', foo=1, bar=2, baz=3
        )

    def test_from_dir(self):
        """Test service reading.
        """
        mock_svc_dir = os.path.join(self.root, 'my_svc')
        os.mkdir(mock_svc_dir)
        with open(os.path.join(mock_svc_dir, 'type'), 'w') as f:
            f.write('longrun')
        with open(os.path.join(mock_svc_dir, 'run'), 'w') as f:
            f.write('mock run script')
        with open(os.path.join(mock_svc_dir, 'down'), 'w') as f:
            pass
        with open(os.path.join(mock_svc_dir, 'notification-fd'), 'w') as f:
            f.write('42')
        os.mkdir(os.path.join(mock_svc_dir, 'data'))
        os.mkdir(os.path.join(mock_svc_dir, 'env'))
        with open(os.path.join(mock_svc_dir, 'env', 'HOME'), 'w') as f:
            f.write('/my/home\n')
        with open(os.path.join(mock_svc_dir, 'env', 'FOO'), 'w') as f:
            f.write('bar\n')

        mock_svc = services.Service.from_dir(mock_svc_dir)

        self.assertIsNotNone(mock_svc)
        self.assertEquals(
            mock_svc.directory,
            os.path.join(self.root, 'my_svc')
        )
        self.assertEquals(mock_svc.type, services.ServiceType.LongRun)
        self.assertEquals(mock_svc.run_script, 'mock run script')
        self.assertEquals(mock_svc.default_down, True)
        self.assertEquals(mock_svc.notification_fd, 42)
        self.assertEquals(
            mock_svc.data_dir,
            os.path.join(self.root, 'my_svc', 'data')
        )
        self.assertEquals(
            mock_svc.env_dir,
            os.path.join(self.root, 'my_svc', 'env')
        )
        self.assertEquals(
            mock_svc.environ,
            {
                'FOO': 'bar',
                'HOME': '/my/home',
            }
        )


if __name__ == '__main__':
    unittest.main()
