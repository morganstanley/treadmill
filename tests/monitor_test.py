"""Unit test for monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import io
import json
import os
import shutil
import tempfile
import unittest

import mock

import treadmill
from treadmill import fs
from treadmill import monitor
from treadmill import subproc
from treadmill import supervisor


class MonitorTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorContainerDown.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.supervisor.open_service', mock.Mock(spec_set=True))
    @mock.patch('treadmill.dirwatch.DirWatcher', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    def test__add_service(self, mock_policy, mock_down_action, mock_dirwatch):
        """Test addition of a service to a running monitor.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs=None,
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = \
            monitor.MonitorRestartPolicyResult.NOOP
        mock_reg_handle = mock_pol_inst.register.return_value
        mock_svc = treadmill.supervisor.open_service.return_value
        mon._dirwatcher = mock_dirwatch()

        mon._add_service(self.root)

        treadmill.supervisor.open_service.assert_called_with(self.root)
        mock_pol_inst.register.assert_called_with(mock_svc)
        self.assertEqual(
            mon._service_policies[mock_reg_handle],
            mock_pol_inst
        )
        mon._dirwatcher.add_dir.assert_called_with(mock_reg_handle)
        self.assertTrue(mock_pol_inst.check.called)

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._add_service',
                mock.Mock(spec_set=True))
    def test__on_created_svc(self, mock_policy, mock_down_action):
        """Test new service created event.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs=('/some/dir', '/some/dir2'),
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )

        mon._on_created('/some/dir2/new')

        treadmill.monitor.Monitor._add_service.assert_called_with(
            '/some/dir2/new'
        )

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._add_service',
                mock.Mock(spec_set=True))
    def test__on_created_exit(self, mock_policy, mock_down_action):
        """Test service exit event.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = \
            monitor.MonitorRestartPolicyResult.FAIL
        mock_pol_inst.fail_reason = {'mock': 'data'}
        mon._service_policies['/some/dir/svc/data/exits'] = mock_pol_inst

        mon._on_created('/some/dir/svc/data/exits/1.111,2,3')
        mon._on_created('/some/dir/svc/data/exits/1.112,2,3')

        self.assertTrue(mock_pol_inst.check.called)
        self.assertEqual(
            list(mon._down_reasons),
            [
                {'mock': 'data'},
                {'mock': 'data'},
            ]
        )
        self.assertFalse(treadmill.monitor.Monitor._add_service.called)

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.supervisor.wait_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.control_service',
                mock.Mock(spec_set=True))
    def test__bring_up(self, mock_policy, mock_down_action):
        """Test interface with supervisor bringing up services.
        """
        # pylint: disable=protected-access
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        treadmill.supervisor.wait_service.side_effect = [
            subproc.CalledProcessError(supervisor.ERR_TIMEOUT, 's6-svwait'),
            None,
        ]

        mon._bring_up(mock_pol_inst.service)

        supervisor.wait_service.assert_has_calls(
            [
                mock.call(mock_pol_inst.service.directory,
                          supervisor.ServiceWaitAction.up,
                          timeout=100),
                mock.call(mock_pol_inst.service.directory,
                          supervisor.ServiceWaitAction.really_down,
                          timeout=60 * 1000),
            ]
        )
        treadmill.supervisor.control_service.assert_called_with(
            mock_pol_inst.service.directory,
            treadmill.supervisor.ServiceControlAction.up
        )

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.supervisor.wait_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.control_service',
                mock.Mock(spec_set=True))
    def test__bring_up_already_up(self, mock_policy, mock_down_action):
        """Test interface with supervisor bringing up services.

        Service already up.
        """
        # pylint: disable=protected-access
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value

        mon._bring_up(mock_pol_inst.service)

        supervisor.wait_service.assert_called_with(
            mock_pol_inst.service.directory,
            supervisor.ServiceWaitAction.up,
            timeout=100
        )
        treadmill.supervisor.control_service.assert_not_called()

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.supervisor.wait_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.control_service',
                mock.Mock(spec_set=True))
    def test__bring_up_no_sup(self, mock_policy, mock_down_action):
        """Test interface with supervisor bringing up services.

        Service not supervised.
        """
        # pylint: disable=protected-access
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        treadmill.supervisor.wait_service.side_effect = (
            subproc.CalledProcessError(supervisor.ERR_NO_SUP, 's6-svwait')
        )

        mon._bring_up(mock_pol_inst.service)

        supervisor.wait_service.assert_called_with(
            mock_pol_inst.service.directory,
            supervisor.ServiceWaitAction.up,
            timeout=100
        )
        treadmill.supervisor.control_service.assert_not_called()

    @mock.patch('treadmill.supervisor.wait_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.control_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.monitor.MonitorEventHook', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._bring_up', spec_set=True)
    def test_event_hook_success(self, mock_bring_up, mock_policy,
                                mock_down_action, mock_event_hook):
        """Test monitor up/down event hook.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_event_hook_inst = mock_event_hook.return_value
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action(),
            event_hook=mock_event_hook_inst
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = \
            monitor.MonitorRestartPolicyResult.RESTART

        mon._process(mock_pol_inst)

        self.assertTrue(mock_pol_inst.check.called)
        self.assertEqual(len(mon._down_reasons), 0)
        self.assertTrue(mock_event_hook_inst.down.called)
        self.assertTrue(mock_event_hook_inst.up.called)
        mock_bring_up.assert_called()

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._bring_up', spec_set=True)
    def test__process_noop(self, mock_bring_up, mock_policy, mock_down_action):
        """Test monitor noop event.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = \
            monitor.MonitorRestartPolicyResult.NOOP

        mon._process(mock_pol_inst)

        self.assertTrue(mock_pol_inst.check.called)
        mock_bring_up.assert_not_called()
        self.assertEqual(len(mon._down_reasons), 0)

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._bring_up', spec_set=True)
    def test__process_success(self, mock_bring_up, mock_policy,
                              mock_down_action):
        """Test monitor success event.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_service_class = collections.namedtuple(
            'MockSvc', ['name', 'directory']
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = (
            monitor.MonitorRestartPolicyResult.RESTART
        )
        mock_pol_inst.service.return_value = (
            mock_service_class('mock_service', 'some_dir')
        )

        mon._process(mock_pol_inst)

        self.assertTrue(mock_pol_inst.check.called)
        self.assertEqual(len(mon._down_reasons), 0)
        mock_bring_up.assert_called()

    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._bring_up', spec_set=True)
    def test__process_fail(self, mock_policy, mock_down_action, mock_bring_up):
        """Test monitor fail event.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs='/some/dir',
            service_dirs=None,
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.check.return_value = \
            monitor.MonitorRestartPolicyResult.FAIL
        type(mock_pol_inst).fail_reason = mock.PropertyMock(return_value={
            'a': 'test'
        })

        mon._process(mock_pol_inst)

        self.assertTrue(mock_pol_inst.check.called)
        mock_bring_up.assert_not_called()
        self.assertEqual(list(mon._down_reasons), [{'a': 'test'}])

    @mock.patch('os.listdir', mock.Mock(spec_set=True, side_effect=[
        ['baz'], ['baz']]))
    @mock.patch('treadmill.supervisor.open_service', mock.Mock(spec_set=True))
    @mock.patch('treadmill.dirwatch.DirWatcher', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorDownAction', spec_set=True)
    @mock.patch('treadmill.monitor.MonitorPolicy', spec_set=True)
    @mock.patch('treadmill.monitor.Monitor._add_service',
                mock.Mock(spec_set=True))
    def test_run(self, mock_policy, mock_down_action, mock_dirwatch):
        """Test monitor run loop.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mon = monitor.Monitor(
            scan_dirs=(
                os.path.join(os.sep, 'some', 'dir'),
                os.path.join(os.sep, 'some', 'dir2')
            ),
            service_dirs=('foo', 'bar'),
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_down_action_inst = mock_down_action.return_value
        mock_down_action_inst.execute.side_effect = [
            True, False,  # First failure is fine, second stops the monitor
        ]
        mock_dirwatch_inst = mock_dirwatch.return_value

        def _mock_policy_down():
            mon._down_reasons = collections.deque(
                [
                    {'mock': 'data'},
                    {'more': 'data'},
                    {'again': 'data'},
                ]
            )

        mock_dirwatch_inst.process_events.side_effect = \
            _mock_policy_down

        mon.run()

        mock_dirwatch_inst.add_dir.assert_has_calls([
            mock.call(os.path.join(os.sep, 'some', 'dir')),
            mock.call(os.path.join(os.sep, 'some', 'dir2'))
        ], any_order=True)
        treadmill.monitor.Monitor._add_service.assert_has_calls(
            [
                mock.call('foo'),
                mock.call('bar'),
                mock.call(os.path.join(os.sep, 'some', 'dir2', 'baz')),
                mock.call(os.path.join(os.sep, 'some', 'dir', 'baz')),
            ],
            any_order=True
        )
        self.assertEqual(
            treadmill.monitor.Monitor._add_service.call_count,
            4
        )
        self.assertTrue(mock_dirwatch.called)
        self.assertTrue(mock_dirwatch_inst.wait_for_events.called)
        self.assertTrue(mock_dirwatch_inst.process_events.called)
        mock_down_action_inst.execute.assert_has_calls(
            [
                mock.call({'mock': 'data'}),
                mock.call({'more': 'data'}),
            ]
        )
        # Make sure the down_reasons queue wasn't cleared (since one of the
        # down actions took down the monitor.
        self.assertEqual(len(mon._down_reasons), 3)


class MonitorContainerCleanupTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorContainerCleanup.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('os.replace', mock.Mock())
    @mock.patch('treadmill.supervisor.control_svscan', mock.Mock())
    @mock.patch('treadmill.appcfg.abort.flag_aborted', mock.Mock())
    def test_execute(self):
        """Test shutting down of the node.
        """
        mock_tm_env_class = collections.namedtuple(
            'MockTMEnv', ['running_dir', 'cleanup_dir']
        )
        mock_tm_env = mock_tm_env_class(os.path.join(self.root, 'running'),
                                        os.path.join(self.root, 'cleanup'))

        service_dir = os.path.join(mock_tm_env.running_dir, 'mock_service')
        fs.mkdir_safe(service_dir)

        with io.open(os.path.join(service_dir, 'type'), 'w') as f:
            f.write('longrun')

        mock_container_cleanup_action =\
            monitor.MonitorContainerCleanup(mock_tm_env)

        res = mock_container_cleanup_action.execute(
            {
                'signal': 0,
                'service': 'mock_service',
            }
        )

        # This MonitorContainerCleanup stops the monitor.
        self.assertEqual(res, True)

        treadmill.appcfg.abort.flag_aborted.assert_not_called()
        os.replace.assert_called()

        supervisor.control_svscan.assert_called_with(
            os.path.join(self.root, 'running'), [
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ]
        )

    @mock.patch('os.replace', mock.Mock())
    @mock.patch('treadmill.supervisor.control_svscan', mock.Mock())
    @mock.patch('treadmill.appcfg.abort.flag_aborted', mock.Mock())
    def test_execute_pid1_aborted(self):
        """Test shutting down of the node.
        """
        mock_tm_env_class = collections.namedtuple(
            'MockTMEnv', ['running_dir', 'cleanup_dir']
        )
        mock_tm_env = mock_tm_env_class(os.path.join(self.root, 'running'),
                                        os.path.join(self.root, 'cleanup'))

        service_dir = os.path.join(mock_tm_env.running_dir, 'mock_service')
        fs.mkdir_safe(service_dir)

        with io.open(os.path.join(service_dir, 'type'), 'w') as f:
            f.write('longrun')

        mock_container_cleanup_action =\
            monitor.MonitorContainerCleanup(mock_tm_env)

        res = mock_container_cleanup_action.execute(
            {
                'signal': 6,
                'service': 'mock_service',
            }
        )

        # This MonitorContainerCleanup stops the monitor.
        self.assertEqual(res, True)

        treadmill.appcfg.abort.flag_aborted.assert_called_with(
            os.path.join(service_dir, 'data'),
            why=treadmill.appcfg.abort.AbortedReason.PID1
        )
        os.replace.assert_called()

        supervisor.control_svscan.assert_called_with(
            os.path.join(self.root, 'running'), [
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ]
        )


class MonitorContainerDownTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorContainerDown.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.supervisor.open_service',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.supervisor.control_service',
                mock.Mock(spec_set=True))
    @mock.patch('os.replace', mock.Mock())
    def test_execute(self):
        """Test shutting down of the container services.
        """
        mock_service_class = collections.namedtuple(
            'MockSvc', ['data_dir', 'directory']
        )
        treadmill.supervisor.open_service.return_value = \
            mock_service_class(self.root, self.root)

        mock_container_cleanup_action =\
            monitor.MonitorContainerDown(self.root)

        res = mock_container_cleanup_action.execute(
            {
                'service': 'mock_service',
            }
        )

        self.assertEqual(res, False)
        self.assertTrue(os.replace.called)
        self.assertTrue(treadmill.supervisor.control_service.called)


class MonitorNodeDownTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorNodeDown.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_execute(self):
        """Test shutting down of the node.
        """
        mock_tm_env_class = collections.namedtuple(
            'MockTMEnv', ['watchdog_dir']
        )
        mock_tm_env = mock_tm_env_class(self.root)
        mock_down_action = monitor.MonitorNodeDown(mock_tm_env)

        res = mock_down_action.execute(
            {
                'service': 'mock_service',
                'return_code': 42,
                'signal': 9,
            }
        )

        # This MonitorDownAction stops the monitor.
        self.assertEqual(res, True)
        self.assertTrue(
            os.path.exists(os.path.join(self.root, 'Monitor-mock_service'))
        )


class MonitorRestartPolicyTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorRestartPolicy.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_noop(self):
        """Test policy evaluation when the service never exited.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.NOOP)
        self.assertIsNone(mock_policy._last_timestamp)
        self.assertIsNone(mock_policy._last_rc)
        self.assertIsNone(mock_policy._last_signal)
        self.assertEqual(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_restart(self):
        """Test policy evaluation when the service should be restarted.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        failure_ts = [1, 2, 3, 75.431, 100.403, 115.871, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEqual(mock_policy._last_timestamp, 130.35)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(
            os.unlink.call_count,
            # We should remove extra exit records past 2 times the policy limit
            len(failure_ts) - 2 * mock_policy._policy_limit
        )

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_restart_egde(self):
        """Test policy evaluation when the service should be restarted.
        (edge case)
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 60
        mock_policy._policy_limit = 1

        failure_ts = [
            1492807053.785,
            1492807113.934,
        ]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEqual(mock_policy._last_timestamp, 1492807113.934)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_fail(self):
        """Test policy evaluation when the service failed too many times.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        failure_ts = [100.403, 115.871, 124, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.FAIL)
        self.assertEqual(mock_policy._last_timestamp, 130.35)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_fail_edge(self):
        """Test policy evaluation when the service failed too many times.
        (edge case)
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 0

        failure_ts = [1.111]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.FAIL)
        self.assertEqual(mock_policy._last_timestamp, 1.111)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(os.unlink.call_count, 0)

    @mock.patch('os.listdir', mock.Mock(
        side_effect=OSError(2, 'No such file or directory')))
    def test__check_listdir_fail(self):
        """Test policy evaluation when the exits dir was deleted.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.NOOP)

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock(spec_set=True))
    @mock.patch('json.load', mock.Mock(spec_set=True))
    def test_register(self):
        """Test policy / service registration.
        """
        mock_service_class = collections.namedtuple(
            'MockSvc', ['name', 'data_dir']
        )
        mock_policy = monitor.MonitorRestartPolicy()
        mock_service = mock_service_class(
            name='mock_service',
            data_dir=os.path.join(self.root)
        )
        json.load.return_value = {
            'limit': 3,
            'interval': 15,
        }

        res = mock_policy.register(mock_service)

        # Check policy.json was read
        io.open.assert_called_with(os.path.join(self.root, 'policy.json'))
        treadmill.fs.mkdir_safe.assert_called_with(
            os.path.join(self.root, 'exits')
        )
        # Registration should return the exits folder to watch
        self.assertEqual(
            res,
            os.path.join(self.root, 'exits')
        )

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock(spec_set=True))
    def test_register_failure(self):
        """Test policy / service registration failure (not policy).
        """
        mock_service_class = collections.namedtuple(
            'MockSvc', ['name', 'data_dir']
        )
        mock_policy = monitor.MonitorRestartPolicy()
        mock_service = mock_service_class(
            name='mock_service',
            data_dir=os.path.join(self.root)
        )
        io.open.side_effect = \
            IOError(errno.ENOENT, 'No such file or directory.')

        res = mock_policy.register(mock_service)

        # Check policy.json was read
        io.open.assert_called_with(os.path.join(self.root, 'policy.json'))
        treadmill.fs.mkdir_safe.assert_not_called()
        # Failed registration should return None
        self.assertIsNone(res)

    def test_fail_reason(self):
        """Test failure reason extraction from the policy.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._last_timestamp = 42.123
        mock_policy._last_rc = 2
        mock_policy._last_signal = 9

        self.assertEqual(
            mock_policy.fail_reason,
            {
                'service': 'mock_service',
                'return_code': 2,
                'signal': 9,
                'timestamp': 42.123,
            }
        )

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    @mock.patch('os.path.islink', mock.Mock(spec_set=True))
    def test__check_cleanup_policy_restart(self):
        """Test cleanup policy evaluation when the cleanup file exits and the
        service should be restarted.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name',
                                                                'directory'])
        mock_tmenv_class = collections.namedtuple('MockTmEnv', ['cleanup_dir'])
        mock_tmenv = mock_tmenv_class(self.root)
        mock_policy = monitor.CleanupMonitorRestartPolicy(mock_tmenv)
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service', self.root)
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        os.path.islink.side_effect = [True]

        failure_ts = [1, 2, 3, 75.431, 100.403, 115.871, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEqual(mock_policy._last_timestamp, 130.35)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(
            os.unlink.call_count,
            # We should remove extra exit records past 2 times the policy limit
            len(failure_ts) - 2 * mock_policy._policy_limit)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    @mock.patch('os.path.islink', mock.Mock(spec_set=True))
    def test__check_cleanup_policy_noop(self):
        """Test cleanup policy evaluation when the cleanup file does not exist.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = collections.namedtuple('MockSvc', ['name',
                                                                'directory'])
        mock_tmenv_class = collections.namedtuple('MockTmEnv', ['cleanup_dir'])
        mock_tmenv = mock_tmenv_class(self.root)
        mock_policy = monitor.CleanupMonitorRestartPolicy(mock_tmenv)
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service', self.root)
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        os.path.islink.side_effect = [True]

        failure_ts = [1, 2, 3, 75.431, 100.403, 115.871, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with io.open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy.check()

        self.assertEqual(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEqual(mock_policy._last_timestamp, 130.35)
        self.assertEqual(mock_policy._last_rc, 1)
        self.assertEqual(mock_policy._last_signal, 0)
        self.assertEqual(
            os.unlink.call_count,
            # We should remove extra exit records past 2 times the policy limit
            len(failure_ts) - 2 * mock_policy._policy_limit)


if __name__ == '__main__':
    unittest.main()
