"""Unit test for supervisor
"""

import os
import re
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

import treadmill
from treadmill import fs
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
            aliases_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'etc',
                             'linux.aliases'))
            os.environ['TREADMILL_ALIASES_PATH'] = ':'.join(aliases_path)

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

    def test_create_service(self):
        """Checks various options when creating the service."""
        supervisor.create_service(
            self.root, 'proid1', 'proid1_home', 'proid1_shell',
            'xx', 'ls -al',
            env='dev'
        )
        service_dir = os.path.join(self.root, 'xx')
        self.assertTrue(os.path.isdir(service_dir))
        self.assertTrue(os.path.isfile(service_dir + '/app_start'))
        self.assertTrue(os.path.isfile(service_dir + '/run'))
        self.assertTrue(os.path.isfile(service_dir + '/finish'))
        self.assertTrue(os.path.isfile(service_dir + '/down'))

        # as_root False, proid is None => Use current UID
        supervisor.create_service(
            self.root, None, 'home', 'shell',
            'bla', 'ls -al',
            env='dev', as_root=False)
        service_dir = os.path.join(self.root, 'bla')

        # Do not create down file.
        supervisor.create_service(
            self.root, 'proid1', 'proid1_home', 'proid1_shell',
            'bar', 'ls -al',
            env='dev', down=False
        )
        service_dir = os.path.join(self.root, 'bar')
        self.assertFalse(os.path.exists(service_dir + '/down'))

    @mock.patch('time.time', mock.Mock(return_value=1000))
    def test_state_parse(self):
        """Test parsing of the s6-svstat output."""
        # Disable W0212: accessing protected member
        # pylint: disable=W0212

        self.assertEquals({'since': 990,
                           'state': 'up',
                           'intended': 'up',
                           'pid': 123},
                          supervisor._parse_state('up (pid 123) 10 seconds\n'))
        self.assertEquals({'since': 900,
                           'state': 'up',
                           'intended': 'down',
                           'pid': 123},
                          supervisor._parse_state('up (pid 123) 100 seconds'
                                                  ' normally down\n'))
        self.assertEquals({'since': 900,
                           'state': 'down',
                           'intended': 'down',
                           'pid': None},
                          supervisor._parse_state('down 100 seconds'))
        self.assertEquals({'since': 900,
                           'state': 'down',
                           'intended': 'up',
                           'pid': None},
                          supervisor._parse_state('down 100 seconds'
                                                  ' normally up'))

    @mock.patch('treadmill.subproc.check_call', mock.Mock(return_value=0))
    def test_wait(self):
        """Test waiting for service status change."""
        # Disable W0212: accessing protected member
        # pylint: disable=W0212

        svcroot = os.path.join(self.root, 'xxx')
        fs.mkdir_safe(os.path.join(svcroot, 'a'))
        fs.mkdir_safe(os.path.join(svcroot, 'b'))
        supervisor._service_wait(svcroot, '-u', '-o')
        expected_cmd = ['s6_svwait', '-u', '-t', '0', '-o',
                        svcroot + '/a', svcroot + '/b']
        actual_cmd = treadmill.subproc.check_call.call_args[0][0]
        self.assertItemsEqual(expected_cmd, actual_cmd)
        treadmill.subproc.check_call.assert_called_with(actual_cmd)

        treadmill.subproc.check_call.reset_mock()
        supervisor._service_wait(svcroot, '-u', '-o', subset=['a'])
        treadmill.subproc.check_call.assert_called_with(['s6_svwait', '-u',
                                                         '-t', '0', '-o',
                                                         svcroot + '/a'])

        treadmill.subproc.check_call.reset_mock()
        supervisor._service_wait(svcroot, '-u', '-o', subset={'a': 1})
        treadmill.subproc.check_call.assert_called_with(['s6_svwait', '-u',
                                                         '-t', '0', '-o',
                                                         svcroot + '/a'])

        treadmill.subproc.check_call.reset_mock()
        supervisor._service_wait(svcroot, '-u', '-o', subset=[])
        self.assertFalse(treadmill.subproc.check_call.called)


if __name__ == '__main__':
    unittest.main()
