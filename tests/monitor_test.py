"""Unit tests for monitor
"""

import os
import shutil
import tempfile
import unittest

from collections import namedtuple

import mock
import yaml

import treadmill
from treadmill import monitor


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
            services_dir=None,
            service_dirs=(),
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_reg_handle = mock_pol_inst.register.return_value
        mock_svc = treadmill.supervisor.open_service.return_value
        mon._dirwatcher = mock_dirwatch()

        mon._add_service(self.root)

        treadmill.supervisor.open_service.assert_called_with(self.root)
        mock_pol_inst.register.assert_called_with(mock_svc)
        self.assertEquals(
            mon._service_policies[mock_reg_handle],
            mock_pol_inst
        )
        mon._dirwatcher.add_dir.assert_called_with(mock_reg_handle)
        self.assertTrue(mock_pol_inst.process.called)

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
            services_dir='/some/dir',
            service_dirs=(),
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )

        mon._on_created('/some/dir/new')

        treadmill.monitor.Monitor._add_service.assert_called_with(
            '/some/dir/new'
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
            services_dir='/some/dir',
            service_dirs=(),
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_pol_inst = mock_policy.return_value
        mock_pol_inst.process.return_value = False
        mock_pol_inst.fail_reason = {'mock': 'data'}
        mon._service_policies['/some/dir/svc/data/exits'] = mock_pol_inst

        mon._on_created('/some/dir/svc/data/exits/1.111,2,3')

        self.assertTrue(mock_pol_inst.process.called)
        self.assertEquals(mon._down_reason, {'mock': 'data'})
        self.assertFalse(treadmill.monitor.Monitor._add_service.called)

    @mock.patch('os.listdir', mock.Mock(spec_set=True, return_value=['baz']))
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
        mock_down_action_inst = mock_down_action.return_value
        mon = monitor.Monitor(
            services_dir='/some/dir',
            service_dirs=('foo', 'bar'),
            policy_impl=mock_policy,
            down_action=mock_down_action()
        )
        mock_down_action_inst.execute.return_value = False
        mock_dirwatch_inst = mock_dirwatch.return_value

        def _mock_policy_down():
            mon._down_reason = {'mock': 'data'}

        mock_dirwatch_inst.process_events.side_effect = \
            _mock_policy_down

        mon.run()

        mock_dirwatch_inst.add_dir.assert_called_with('/some/dir')
        treadmill.monitor.Monitor._add_service.assert_has_calls(
            [
                mock.call('foo'),
                mock.call('bar'),
                mock.call('/some/dir/baz'),
            ]
        )
        self.assertEquals(
            treadmill.monitor.Monitor._add_service.call_count,
            3
        )
        self.assertTrue(mock_dirwatch.called)
        self.assertTrue(mock_dirwatch_inst.wait_for_events.called)
        self.assertTrue(mock_dirwatch_inst.process_events.called)
        mock_down_action_inst.execute.assert_called_with({'mock': 'data'})
        self.assertIsNone(mon._down_reason)


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
        mock_tm_env_class = namedtuple('MockTMEnv', ['watchdog_dir'])
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
        self.assertEquals(res, True)
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

        res = mock_policy._check_policy()

        self.assertEquals(res, monitor.MonitorRestartPolicyResult.NOOP)
        self.assertIsNone(mock_policy._last_timestamp)
        self.assertIsNone(mock_policy._last_rc)
        self.assertIsNone(mock_policy._last_signal)
        self.assertEquals(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_restart(self):
        """Test policy evaluation when the service should be restarted.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        failure_ts = [1, 2, 3, 75.431, 100.403, 115.871, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy._check_policy()

        self.assertEquals(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEquals(mock_policy._last_timestamp, 130.35)
        self.assertEquals(mock_policy._last_rc, 1)
        self.assertEquals(mock_policy._last_signal, 0)
        self.assertEquals(
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
        mock_service_class = namedtuple('MockSvc', ['name'])
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
            with open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy._check_policy()

        self.assertEquals(res, monitor.MonitorRestartPolicyResult.RESTART)
        self.assertEquals(mock_policy._last_timestamp, 1492807113.934)
        self.assertEquals(mock_policy._last_rc, 1)
        self.assertEquals(mock_policy._last_signal, 0)
        self.assertEquals(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_fail(self):
        """Test policy evaluation when the service failed too many times.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3

        failure_ts = [100.403, 115.871, 124, 130.35]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy._check_policy()

        self.assertEquals(res, monitor.MonitorRestartPolicyResult.FAIL)
        self.assertEquals(mock_policy._last_timestamp, 130.35)
        self.assertEquals(mock_policy._last_rc, 1)
        self.assertEquals(mock_policy._last_signal, 0)
        self.assertEquals(os.unlink.call_count, 0)

    @mock.patch('os.unlink', mock.Mock(spec_set=True))
    def test__check_policy_fail_edge(self):
        """Test policy evaluation when the service failed too many times.
        (edge case)
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 0

        failure_ts = [1.111]
        for ts in failure_ts:
            exit_file = '%014.3f,001,000' % ts
            with open(os.path.join(self.root, exit_file), 'a'):
                pass

        res = mock_policy._check_policy()

        self.assertEquals(res, monitor.MonitorRestartPolicyResult.FAIL)
        self.assertEquals(mock_policy._last_timestamp, 1.111)
        self.assertEquals(mock_policy._last_rc, 1)
        self.assertEquals(mock_policy._last_signal, 0)
        self.assertEquals(os.unlink.call_count, 0)

    @mock.patch('builtins.open', autospec=True)
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock(spec_set=True))
    @mock.patch('yaml.load', mock.Mock(spec_set=True))
    def test_register(self, mock_open):
        """Test policy / service registration.
        """
        mock_service_class = namedtuple('MockSvc', ['name', 'data_dir'])
        (os.path.join(self.root))
        mock_policy = monitor.MonitorRestartPolicy()
        mock_service = mock_service_class(
            name='mock_service',
            data_dir=os.path.join(self.root)
        )
        yaml.load.return_value = {
            'limit': 3,
            'interval': 15,
        }

        res = mock_policy.register(mock_service)

        # Check policy.yml was read
        mock_open.assert_called_with(os.path.join(self.root, 'policy.yml'))
        treadmill.fs.mkdir_safe.assert_called_with(
            os.path.join(self.root, 'exits')
        )
        # Registration should return the exits folder to watch
        self.assertEquals(
            res,
            os.path.join(self.root, 'exits')
        )

    @mock.patch('treadmill.monitor.MonitorRestartPolicy._check_policy',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_process_noop(self):
        """Test watch event processing.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name', 'directory'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service', 'some_dir')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3
        mock_policy._check_policy.return_value = \
            monitor.MonitorRestartPolicyResult.NOOP

        res = mock_policy.process()

        self.assertEquals(res, True)
        self.assertEquals(treadmill.subproc.check_call.call_count, 0)

    @mock.patch('treadmill.monitor.MonitorRestartPolicy._check_policy',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_process_success(self):
        """Test watch event processing.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name', 'directory'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service', 'some_dir')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3
        mock_policy._check_policy.return_value = \
            monitor.MonitorRestartPolicyResult.RESTART

        res = mock_policy.process()

        self.assertEquals(res, True)
        self.assertEquals(treadmill.subproc.check_call.call_count, 1)
        treadmill.subproc.check_call.assert_called_with(
            [
                's6_svc',
                '-u',
                'some_dir'
            ]
        )

    @mock.patch('treadmill.monitor.MonitorRestartPolicy._check_policy',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test_process_fail(self):
        """Test watch event processing.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name', 'directory'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service_exits_log = self.root
        mock_policy._service = mock_service_class('mock_service', 'some_dir')
        mock_policy._policy_interval = 30
        mock_policy._policy_limit = 3
        mock_policy._check_policy.return_value = \
            monitor.MonitorRestartPolicyResult.FAIL

        res = mock_policy.process()

        self.assertEquals(res, False)
        self.assertEquals(treadmill.subproc.check_call.call_count, 0)

    def test_fail_reason(self):
        """Test failure reason extraction from the policy.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        mock_service_class = namedtuple('MockSvc', ['name'])
        mock_policy = monitor.MonitorRestartPolicy()
        mock_policy._service = mock_service_class('mock_service')
        mock_policy._last_timestamp = 42.123
        mock_policy._last_rc = 2
        mock_policy._last_signal = 9

        self.assertEquals(
            mock_policy.fail_reason,
            {
                'service': 'mock_service',
                'return_code': 2,
                'signal': 9,
                'timestamp': 42.123,
            }
        )


if __name__ == '__main__':
    unittest.main()
