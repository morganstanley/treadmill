"""Unit test for supervisor.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import collections
import os
import pwd
import re
import shutil
import tempfile
import unittest

import mock
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

import treadmill
from treadmill import supervisor
from treadmill import subproc

# Disable: C0103 because names are too long
# pylint: disable=C0103


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
        aliases_path = os.environ.get('TREADMILL_ALIASES_PATH')
        if aliases_path is None:
            os.environ['TREADMILL_ALIASES_PATH'] = 'node:node.ms'

        os.environ['PATH'] = ':'.join(os.environ['PATH'].split(':') + [
            os.path.join(subproc.resolve('s6'), 'bin')
        ])

    def setUp(self):
        self.mock_pwrow = collections.namedtuple(
            'mock_pwrow',
            ['pw_shell', 'pw_dir']
        )
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        os.system('pgrep s6-svscan | xargs kill 2> /dev/null')
        os.system('pgrep s6-supervise | xargs kill 2> /dev/null')

    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    def test_create_service(self):
        """Checks various options when creating the service.
        """
        pwd.getpwnam.return_value = self.mock_pwrow('test_shell', 'test_home')

        supervisor.create_service(
            self.root,
            'xx',
            'proid1',
            'ls -al',
            downed=True
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        data_dir = os.path.join(service_dir, 'data')
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'app_start')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'run')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'finish')))
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

    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    def test_create_service_optional(self):
        """Checks optional components of create service.
        """
        pwd.getpwnam.return_value = self.mock_pwrow('test_shell', 'test_home')
        svc_dir = supervisor.create_scan_dir(self.root, 5000)

        supervisor.create_service(
            svc_dir,
            'xx',
            'proid1',
            'ls -al',
            monitor_policy={
                'a': 'test1'
            },
            environ={
                'b': 'test2'
            },
            trace={
                'c': 'test3'
            }
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        data_dir = os.path.join(service_dir, 'data')
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'app_start')))
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'trace')))
        self.assertTrue(os.path.isfile(os.path.join(data_dir, 'policy.json')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'run')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'finish')))
        self.assertTrue(os.path.isfile(os.path.join(service_dir, 'env/b')))

    def test_create_service_bad_userid(self):
        """Tests creating a service with a bad userid.
        """
        svc_dir = supervisor.create_scan_dir(self.root, 5000)

        self.assertRaises(
            KeyError,
            supervisor.create_service,
            svc_dir,
            'xx',
            'should not exist',
            'ls -al',
            downed=True
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_is_supervised(self):
        """Tests that checking if a service directory is supervised.
        """
        self.assertTrue(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(['s6_svok', self.root])

        treadmill.subproc.check_call.side_effect = \
            subprocess.CalledProcessError(1, 's6_svok')
        self.assertFalse(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(['s6_svok', self.root])

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_control_service(self):
        """Tests controlling a service.
        """
        self.assertTrue(supervisor.control_service(
            self.root, supervisor.ServiceControlAction.down
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svc', '-d', self.root]
        )

        self.assertTrue(supervisor.control_service(
            self.root, (
                supervisor.ServiceControlAction.up,
                supervisor.ServiceControlAction.once_at_most,
            ),
            timeout=100,  # Should not be used
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svc', '-uO', self.root]
        )

        self.assertTrue(supervisor.control_service(
            self.root, supervisor.ServiceControlAction.up,
            wait=supervisor.ServiceWaitAction.up,
            timeout=100,
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svc', '-wu', '-T100', '-u', self.root]
        )

        treadmill.subproc.check_call.side_effect = \
            subprocess.CalledProcessError(1, 's6_svc')
        self.assertFalse(supervisor.control_service(
            self.root, supervisor.ServiceControlAction.down
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svc', '-d', self.root]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_control_svscan(self):
        """Tests controlling an svscan instance.
        """
        supervisor.control_svscan(
            self.root, (
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            )
        )
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svscanctl', '-an', self.root]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_wait_service(self):
        """Tests waiting on a service.
        """
        self.assertTrue(supervisor.wait_service(
            self.root, supervisor.ServiceWaitAction.down
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svwait', '-d', self.root]
        )

        self.assertTrue(supervisor.wait_service(
            (
                os.path.join(self.root, 'a'),
                os.path.join(self.root, 'b')
            ),
            supervisor.ServiceWaitAction.really_up,
            all_services=False,
            timeout=100,
        ))
        treadmill.subproc.check_call.assert_called_with(
            [
                's6_svwait', '-t100', '-o', '-U',
                os.path.join(self.root, 'a'),
                os.path.join(self.root, 'b')
            ]
        )

        treadmill.subproc.check_call.side_effect = \
            subprocess.CalledProcessError(99, 's6_svwait')
        self.assertFalse(supervisor.wait_service(
            self.root, supervisor.ServiceWaitAction.really_down
        ))
        treadmill.subproc.check_call.assert_called_with(
            ['s6_svwait', '-D', self.root]
        )

    @mock.patch('treadmill.supervisor.is_supervised', mock.Mock())
    def test_ensure_not_supervised_not_running(self):
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
    def test_ensure_not_supervised_kill_exit(self):
        """Tests ensuring a service and its logs when the the service is up
        and running.
        """
        treadmill.supervisor.is_supervised.side_effect = (True, False)
        treadmill.supervisor.is_supervised.control_service.return_value = True

        supervisor.ensure_not_supervised(self.root)

        treadmill.supervisor.control_service.assert_called_with(
            self.root, (supervisor.ServiceControlAction.kill,
                        supervisor.ServiceControlAction.exit),
            supervisor.ServiceWaitAction.really_down,
            timeout=1000
        )

        self.assertEqual(2, treadmill.supervisor.is_supervised.call_count)

    @mock.patch('treadmill.supervisor.is_supervised', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
    @mock.patch('time.sleep', mock.Mock())
    def test_ensure_not_supervised_failed(self):
        """Tests when a service fails to be brought down.
        """
        treadmill.supervisor.is_supervised.return_value = True
        treadmill.supervisor.control_service.side_effect = \
            subprocess.CalledProcessError(1, '')

        with self.assertRaises(Exception):
            supervisor.ensure_not_supervised(self.root)


if __name__ == '__main__':
    unittest.main()
