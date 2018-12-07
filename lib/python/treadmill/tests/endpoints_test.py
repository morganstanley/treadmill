"""Unit test for endpoints.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import io
import os
import shutil
import sys
import tempfile
import unittest

import mock

import treadmill
import treadmill.runtime.runtime_base
from treadmill import appenv
from treadmill import endpoints


# Disable warning about accessing protected members.
#
# pylint: disable=W0212
class PortScannerTest(unittest.TestCase):
    """Mock test for treadmill.endpoints.PortScanner
    """

    @mock.patch('treadmill.appenv.AppEnvironment', mock.Mock(autospec=True))
    @mock.patch('treadmill.watchdog.Watchdog', mock.Mock(autospec=True))
    def setUp(self):
        self.root = tempfile.mkdtemp()

        zkclient = treadmill.zkutils.ZkClient()
        self.scanner = endpoints.PortScanner(self.root, zkclient,
                                             scan_interval=30)
        self.scanner.hostname = 'x.x.com'

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='x.x.com'))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.netutils.netstat',
                mock.Mock(return_value=set([8000])))
    def test_scan(self):
        """Test publishing endpoints status info."""
        endp_files = ['x.y#001~http~tcp~45000~12345~8000']
        for end_p in endp_files:
            io.open(os.path.join(self.root, end_p), 'w').close()
        self.assertEqual(
            {45000: 1},
            self.scanner._scan()
        )
        treadmill.netutils.netstat.assert_called_with('12345')


class EndpointPublisherTest(unittest.TestCase):
    """Mock test for endpoint publisher."""

    @mock.patch('treadmill.appenv.AppEnvironment', mock.Mock(autospec=True))
    @mock.patch('treadmill.watchdog.Watchdog', mock.Mock(autospec=True))
    def setUp(self):
        self.root = tempfile.mkdtemp()
        zkclient = treadmill.zkutils.ZkClient()
        self.publisher = endpoints.EndpointPublisher(
            self.root,
            zkclient,
            instance=None
        )
        self.publisher.hostname = 'x.x.com'

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_publish(self):
        """Test publishing endpoints to Zookeeper."""
        endp_files = ['x.y#001~http~tcp~45000~192.168.0.5~8000',
                      'a.b#001~http~tcp~55000~192.168.0.6~8000']

        for end_p in endp_files:
            io.open(os.path.join(self.root, end_p), 'w').close()

        for path in glob.glob(os.path.join(self.root, '*')):
            self.publisher._on_created(path)

        self.assertEqual(
            self.publisher.state,
            set(['x.y#001:http:tcp:45000', 'a.b#001:http:tcp:55000'])
        )

        self.publisher._publish()
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/discovery/x.x.com',
            ['a.b#001:http:tcp:55000',
             'x.y#001:http:tcp:45000'],
            ephemeral=True,
            acl=mock.ANY
        )


class EndpointMgrTest(unittest.TestCase):
    """Mock test for endpoint manager."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.root, 'endpoints'))
        os.mkdir(os.path.join(self.root, 'apps'))
        self.manager = endpoints.EndpointsMgr(
            os.path.join(self.root, 'endpoints')
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_get_spec(self):
        """Test get endpoint spec with partial pattern match.
        """
        tm_env = appenv.AppEnvironment(root=self.root)
        endpoints_mgr = endpoints.EndpointsMgr(tm_env.endpoints_dir)

        # pylint: disable=W0212
        self.assertIsNone(endpoints_mgr.get_spec())

        endpoints_mgr.create_spec(
            appname='appname##0000000001',
            proto='tcp',
            endpoint='nodeinfo',
            real_port=12345,
            pid=5213,
            port=8000,
            owner=None,
        )
        self.assertIsNotNone(endpoints_mgr.get_spec(proto='tcp'))
        self.assertEqual(
            endpoints_mgr.get_spec(proto='tcp'),
            endpoints_mgr.get_spec(endpoint='nodeinfo'),
        )
        self.assertEqual(
            endpoints_mgr.get_spec(proto='tcp'),
            endpoints_mgr.get_spec(proto='tcp', endpoint='nodeinfo'),
        )

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    def test_createspec(self):
        """Test creation of endpoint spec."""
        owner = os.path.join(self.root, 'apps', 'app1-12345')
        self.manager.create_spec(
            appname='app1',
            proto='tcp',
            endpoint='http',
            real_port=12345,
            pid=4,
            port=8000,
            owner=owner,
        )

        expected = os.path.join(
            self.root,
            'endpoints',
            'app1~tcp~http~12345~4~8000'
        )
        self.assertEqual(
            os.path.join(self.root, 'apps', 'app1-12345'),
            os.readlink(expected)
        )

        endpoints.garbage_collect(os.path.join(self.root, 'endpoints'))
        self.assertRaises(FileNotFoundError, os.readlink, expected)

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    def test_unlink_all(self):
        """Test creation of endpoint spec."""
        owner = os.path.join(self.root, 'apps', 'app1-12345')
        self.manager.create_spec(
            appname='app1',
            proto='tcp',
            endpoint='http',
            real_port=12345,
            pid=4,
            port=8000,
            owner=owner,
        )

        expected = os.path.join(
            self.root,
            'endpoints',
            'app1~tcp~http~12345~4~8000'
        )
        self.assertEqual(
            os.path.join(self.root, 'apps', 'app1-12345'),
            os.readlink(expected)
        )
        self.manager.unlink_all('app1', owner='app1-nosuchinstance')
        self.assertEqual(
            os.path.join(self.root, 'apps', 'app1-12345'),
            os.readlink(expected)
        )
        self.manager.unlink_all('app1', owner='app1-12345')
        self.assertRaises(FileNotFoundError, os.readlink, expected)


if __name__ == '__main__':
    unittest.main()
