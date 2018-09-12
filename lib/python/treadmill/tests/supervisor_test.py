"""Unit test for supervisor.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import collections
import os
import re
import shutil
import sys
import tempfile
import unittest

import mock

import treadmill
from treadmill import supervisor
from treadmill import subproc


def _strip(content):
    """Strips and replaces all spaces before beginning of the text.
    """
    return '\n'.join(
        [re.sub(r'^\s+', '', line) for line in content.split('\n')]).strip()


class SupervisorTest(unittest.TestCase):
    """Tests supervisor routines.
    """

    @classmethod
    def setUpClass(cls):
        subproc.load_packages(['node'])

    def setUp(self):
        self.mock_pwrow = collections.namedtuple(
            'mock_pwrow',
            ['pw_shell', 'pw_dir']
        )
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

        if sys.platform.startswith('linux'):
            os.system('pgrep s6-svscan | xargs kill 2> /dev/null')
            os.system('pgrep s6-supervise | xargs kill 2> /dev/null')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch(
        'pwd.getpwnam',
        mock.Mock(
            spec_set=True,
            return_value=collections.namedtuple(
                'pwnam',
                ['pw_shell', 'pw_dir']
            )('test_shell', 'test_home')
        )
    )
    def test_create_service(self):
        """Checks various options when creating the service.
        """
        supervisor.create_service(
            self.root,
            'xx',
            'ls -al',
            userid='proid1',
            downed=True
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        data_dir = os.path.join(service_dir, 'data')
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'app_start')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'run')))
        self.assertFalse(os.path.isfile(os.path.join(service_dir, 'finish')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'down')))

        # Do not create down file.
        supervisor.create_service(
            self.root,
            'bar',
            'proid1',
            'ls -al',
            downed=False
        )
        service_dir = os.path.join(self.root, 'bar')
        self.assertFalse(os.path.exists(os.path.join(service_dir, 'down')))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch(
        'pwd.getpwnam',
        mock.Mock(
            spec_set=True,
            return_value=collections.namedtuple(
                'pwnam',
                ['pw_shell', 'pw_dir']
            )('test_shell', 'test_home')
        )
    )
    def test_create_service_optional(self):
        """Checks optional components of create service.
        """
        svc_dir = supervisor.create_scan_dir(self.root, 5000)

        supervisor.create_service(
            svc_dir,
            'xx',
            'ls -al',
            userid='proid1',
            monitor_policy={
                'limit': 5,
                'interval': 60,
                'tombstone': {
                    'uds': True,
                    'path': '/run/tm_ctl/tombstone',
                    'id': 'xx'
                }
            },
            environ={
                'b': 'test2'
            },
            trace={
                'instanceid': 'xx',
                'uniqueid': 'ID1234',
                'service': 'xx',
                'path': '/run/tm_ctl/appevents'
            }
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        data_dir = os.path.join(service_dir, 'data')
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'app_start')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'run')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'finish')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'env/b')))

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    def test_create_service_bad_userid(self):
        """Tests creating a service with a bad userid.
        """
        svc_dir = supervisor.create_scan_dir(self.root, 5000)

        self.assertRaises(
            KeyError,
            supervisor.create_service,
            svc_dir,
            'xx',
            'ls -al',
            userid='should not exist',
            downed=True
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_is_supervised(self):
        """Tests that checking if a service directory is supervised.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        self.assertTrue(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svok'), self.root]
        )

        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(1, supervisor._get_cmd('svok'))
        self.assertFalse(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svok'), self.root]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_control_service(self):
        """Tests controlling a service.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        self.assertTrue(supervisor.control_service(
            self.root, supervisor.ServiceControlAction.down
        ))
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-d', self.root]
        )

        self.assertTrue(supervisor.control_service(
            self.root, (
                supervisor.ServiceControlAction.up,
                supervisor.ServiceControlAction.once_at_most,
            ),
            timeout=100,  # Should not be used
        ))
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-uO', self.root]
        )

        self.assertTrue(supervisor.control_service(
            self.root, supervisor.ServiceControlAction.up,
            wait=supervisor.ServiceWaitAction.up,
            timeout=100,
        ))
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-wu', '-T100', '-u', self.root]
        )

        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(1, supervisor._get_cmd('svc'))
        self.assertRaises(
            subproc.CalledProcessError,
            supervisor.control_service,
            self.root,
            supervisor.ServiceControlAction.down
        )
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-d', self.root]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.wait_service', mock.Mock())
    def test_control_service_wait(self):
        """Tests controlling a service and wait"""
        # Disable W0212(protected-access)
        # pylint: disable=W0212

        # shutdown supervised service
        res = supervisor.control_service(
            self.root, supervisor.ServiceControlAction.down,
            wait=supervisor.ServiceWaitAction.down,
            timeout=100,
        )

        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-wd', '-T100', '-d', self.root]
        )
        self.assertTrue(res)

        # shutdown service timeouts
        treadmill.subproc.check_call.reset_mock()
        supervisor.subproc.check_call.side_effect = \
            subproc.CalledProcessError(
                supervisor.ERR_TIMEOUT,
                supervisor._get_cmd('svc')
            )

        res = supervisor.control_service(
            self.root, supervisor.ServiceControlAction.down,
            wait=supervisor.ServiceWaitAction.down,
            timeout=100,
        )
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svc'), '-wd', '-T100', '-d', self.root]
        )
        self.assertFalse(res)

        # shutdown unsupervised service
        treadmill.subproc.check_call.reset_mock()
        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(
                supervisor.ERR_NO_SUP,
                supervisor._get_cmd('svc')
            )

        with self.assertRaises(subproc.CalledProcessError):
            supervisor.control_service(
                self.root, supervisor.ServiceControlAction.down,
                wait=supervisor.ServiceWaitAction.down,
                timeout=100,
            )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_control_svscan(self):
        """Tests controlling an svscan instance.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        supervisor.control_svscan(
            self.root, (
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            )
        )
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svscanctl'), '-an', self.root]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_wait_service(self):
        """Tests waiting on a service.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        supervisor.wait_service(
            self.root, supervisor.ServiceWaitAction.down
        )
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svwait'), '-d', self.root]
        )

        treadmill.subproc.check_call.reset_mock()
        supervisor.wait_service(
            (
                os.path.join(self.root, 'a'),
                os.path.join(self.root, 'b')
            ),
            supervisor.ServiceWaitAction.up,
            all_services=False,
            timeout=100,
        )

        treadmill.subproc.check_call.assert_called_with(
            [
                supervisor._get_cmd('svwait'), '-t100', '-o', '-u',
                os.path.join(self.root, 'a'),
                os.path.join(self.root, 'b')
            ]
        )

        treadmill.subproc.check_call.reset_mock()
        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(99, supervisor._get_cmd('svwait'))
        with self.assertRaises(subproc.CalledProcessError):
            supervisor.wait_service(
                self.root, supervisor.ServiceWaitAction.really_down
            )
        treadmill.subproc.check_call.assert_called_with(
            [supervisor._get_cmd('svwait'), '-D', self.root]
        )

    # Disable: C0103 because names are too long
    @mock.patch('treadmill.supervisor.is_supervised', mock.Mock())
    def test_ensure_not_supervised_not_running(self):  # pylint: disable=C0103
        """Tests ensuring a service and its logs are down when they already
        are not supervised.
        """
        treadmill.supervisor.is_supervised.return_value = False

        supervisor.ensure_not_supervised(self.root)

        treadmill.supervisor.is_supervised.assert_called_once_with(
            self.root
        )

        self.assertEqual(1, treadmill.supervisor.is_supervised.call_count)

        treadmill.supervisor.is_supervised.reset_mock()

        log_dir = os.path.join(self.root, 'log')
        os.mkdir(log_dir)

        supervisor.ensure_not_supervised(self.root)

        treadmill.supervisor.is_supervised.assert_has_calls([
            mock.call(self.root), mock.call(log_dir)
        ])

        self.assertEqual(2, treadmill.supervisor.is_supervised.call_count)

    @mock.patch('treadmill.supervisor.is_supervised', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
    def test_ensure_not_supervised_exit(self):
        """Tests a supervisor was up and waiting to exit.
        """
        treadmill.supervisor.is_supervised.side_effect = (True, False)
        treadmill.supervisor.is_supervised.control_service.return_value = True

        supervisor.ensure_not_supervised(self.root)

        treadmill.supervisor.control_service.assert_called_with(
            self.root, supervisor.ServiceControlAction.exit,
            supervisor.ServiceWaitAction.really_down,
            timeout=1000
        )

        self.assertEqual(2, treadmill.supervisor.is_supervised.call_count)

    # Disable: C0103 because names are too long
    @mock.patch('treadmill.supervisor.is_supervised', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
    @mock.patch('time.sleep', mock.Mock())
    def test_ensure_not_supervised_failed(self):  # pylint: disable=C0103
        """Tests when a service fails to be brought down.
        """
        treadmill.supervisor.is_supervised.return_value = True
        treadmill.supervisor.control_service.side_effect = \
            subproc.CalledProcessError(1, '')

        with self.assertRaises(Exception):
            supervisor.ensure_not_supervised(self.root)


if __name__ == '__main__':
    unittest.main()
