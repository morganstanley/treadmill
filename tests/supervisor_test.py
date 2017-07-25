"""Unit test for supervisor
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

import treadmill
from treadmill import supervisor
from treadmill import subproc


def _strip(content):
    """Strips and replaces all spaces before beginning of the text."""
    return '\n'.join(
        [re.sub(r'^\s+', '', line) for line in content.split('\n')]).strip()


class SupervisorTest(unittest.TestCase):
    """Tests supervisor routines."""

    @classmethod
    def setUpClass(cls):
        aliases_path = os.environ.get('TREADMILL_ALIASES_PATH')
        if aliases_path is None:
            os.environ['TREADMILL_ALIASES_PATH'] = 'node:node.ms'

        os.environ['PATH'] = ':'.join(os.environ['PATH'].split(':') + [
            os.path.join(subproc.resolve('s6'), 'bin')
        ])

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        os.system('pgrep s6-svscan | xargs kill 2> /dev/null')
        os.system('pgrep s6-supervise | xargs kill 2> /dev/null')

    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    def test_create_service(self):
        """Checks various options when creating the service."""
        svc_dir = supervisor.create_scan_dir(self.root, 5000)

        supervisor.create_service(
            svc_dir,
            'xx',
            'proid1',
            'ls -al',
            downed=True
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        data_dir = os.path.join(service_dir, 'data')
        self.assertTrue(os.path.isfile(data_dir + '/app_start'))
        self.assertTrue(os.path.isfile(service_dir + '/run'))
        self.assertTrue(os.path.isfile(service_dir + '/finish'))
        self.assertTrue(os.path.isfile(service_dir + '/down'))

        # Do not create down file.
        supervisor.create_service(
            svc_dir,
            'bar',
            'proid1',
            'ls -al',
            downed=False
        )
        service_dir = os.path.join(self.root, 'bar')
        self.assertFalse(os.path.exists(service_dir + '/down'))

    @mock.patch('pwd.getpwnam', mock.Mock(auto_spec=True))
    def test_create_service_optional(self):
        """Checks optional components of create service."""
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
        self.assertTrue(os.path.isfile(data_dir + '/app_start'))
        self.assertTrue(os.path.isfile(data_dir + '/trace'))
        self.assertTrue(os.path.isfile(data_dir + '/policy.json'))
        self.assertTrue(os.path.isfile(service_dir + '/run'))
        self.assertTrue(os.path.isfile(service_dir + '/finish'))
        self.assertTrue(os.path.isfile(service_dir + '/env/b'))

    def test_create_service_bad_userid(self):
        """Tests creating a service with a bad userid."""
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
        """Tests that checking if a service directory is supervised."""
        self.assertTrue(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(['s6_svok', self.root])

        treadmill.subproc.check_call.side_effect = \
            subprocess.CalledProcessError(1, 's6_svok')
        self.assertFalse(supervisor.is_supervised(self.root))
        treadmill.subproc.check_call.assert_called_with(['s6_svok', self.root])

    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_control_service(self):
        """Tests controlling a service."""
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
            ['s6_svc', '-wu', '-T', '100', '-u', self.root]
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
        """Tests controlling an svscan instance."""
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
        """Tests waiting on a service."""
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
                's6_svwait', '-t', '100', '-o', '-U',
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

if __name__ == '__main__':
    unittest.main()
