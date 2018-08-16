"""Unit test for monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
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
from treadmill import supervisor
from treadmill import utils


class MonitorTest(unittest.TestCase):
    """Mock test for treadmill.monitor.MonitorContainerDown.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.dirwatch.DirWatcher', mock.Mock())
    @mock.patch('treadmill.plugin_manager.load', mock.Mock())
    def test_configure(self):
        """Test monitor run loop.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        config_dir = os.path.join(self.root, 'config')
        watch_dir1 = os.path.join(self.root, 'watch', '1')
        watch_dir2 = os.path.join(self.root, 'watch', '2')

        fs.mkdir_safe(config_dir)
        fs.mkdir_safe(watch_dir1)
        fs.mkdir_safe(watch_dir2)

        with io.open(os.path.join(config_dir, 'default'), 'w') as f:
            f.writelines([
                '{};plugin1\n'.format(watch_dir1),
                '{};plugin2;{{"key": "value"}}\n'.format(watch_dir2)
            ])

        impl1 = mock.Mock()

        # W0613(unused-argument)
        def _handler1(tm_env, params):  # pylint: disable=W0613
            return impl1

        impl2 = mock.Mock()

        # W0613(unused-argument)
        def _handler2(tm_env, params):  # pylint: disable=W0613
            return impl2

        treadmill.plugin_manager.load.side_effect = [_handler1, _handler2]

        mock_dirwatch = mock.Mock()
        treadmill.dirwatch.DirWatcher.return_value = mock_dirwatch
        mock_dirwatch.wait_for_events.side_effect = [
            StopIteration()
        ]

        mon = monitor.Monitor(
            tm_env={},
            config_dir=config_dir
        )

        self.assertRaises(StopIteration, mon.run)
        treadmill.plugin_manager.load.assert_has_calls([
            mock.call('treadmill.tombstones', 'plugin1'),
            mock.call('treadmill.tombstones', 'plugin2'),
        ], any_order=True)
        mock_dirwatch.add_dir.assert_has_calls([
            mock.call(watch_dir1),
            mock.call(watch_dir2),
        ], any_order=True)

    @mock.patch('treadmill.dirwatch.DirWatcher', mock.Mock())
    @mock.patch('treadmill.plugin_manager.load', mock.Mock())
    def test_configure_restart(self):
        """Test monitor run loop.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        config_dir = os.path.join(self.root, 'config')
        watch_dir1 = os.path.join(self.root, 'watch', '1')

        fs.mkdir_safe(config_dir)
        fs.mkdir_safe(watch_dir1)

        event_file = os.path.join(watch_dir1, 'test,12345.123,1,0')
        utils.touch(event_file)

        with io.open(os.path.join(config_dir, 'default'), 'w') as f:
            f.writelines([
                '{};plugin1\n'.format(watch_dir1)
            ])

        impl1 = mock.Mock()
        impl1.execute.return_value = True

        # W0613(unused-argument)
        def _handler1(tm_env, params):  # pylint: disable=W0613
            return impl1

        treadmill.plugin_manager.load.side_effect = [_handler1]

        mock_dirwatch = mock.Mock()
        treadmill.dirwatch.DirWatcher.return_value = mock_dirwatch
        mock_dirwatch.wait_for_events.side_effect = [
            False, StopIteration()
        ]

        mon = monitor.Monitor(
            tm_env={},
            config_dir=config_dir
        )

        self.assertRaises(StopIteration, mon.run)
        impl1.execute.assert_called_with({
            'return_code': 1,
            'id': 'test',
            'signal': 0,
            'timestamp': 12345.123,
        })
        self.assertFalse(os.path.exists(event_file))

    @mock.patch('treadmill.dirwatch.DirWatcher', mock.Mock())
    @mock.patch('treadmill.plugin_manager.load', mock.Mock())
    def test_run(self):
        """Test monitor run loop.
        """
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        config_dir = os.path.join(self.root, 'config')
        watch_dir1 = os.path.join(self.root, 'watch', '1')

        fs.mkdir_safe(config_dir)
        fs.mkdir_safe(watch_dir1)

        event_file = os.path.join(watch_dir1, 'test2,12345.123,256,9')

        with io.open(os.path.join(config_dir, 'default'), 'w') as f:
            f.writelines([
                '{};plugin1\n'.format(watch_dir1)
            ])

        impl1 = mock.Mock()
        impl1.execute.return_value = False

        # W0613(unused-argument)
        def _handler1(tm_env, params):  # pylint: disable=W0613
            return impl1

        treadmill.plugin_manager.load.side_effect = [_handler1]

        def _side_effect():
            utils.touch(event_file)
            return True

        mock_dirwatch = mock.Mock()
        treadmill.dirwatch.DirWatcher.return_value = mock_dirwatch
        mock_dirwatch.wait_for_events.side_effect = [
            _side_effect(), StopIteration()
        ]

        mon = monitor.Monitor(
            tm_env={},
            config_dir=config_dir
        )

        self.assertRaises(StopIteration, mon.run)
        impl1.execute.assert_called_with({
            'return_code': 256,
            'id': 'test2',
            'signal': 9,
            'timestamp': 12345.123,
        })
        self.assertTrue(os.path.exists(event_file))


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
            monitor.MonitorContainerCleanup(mock_tm_env, {})

        res = mock_container_cleanup_action.execute(
            {
                'signal': 0,
                'id': 'mock_service',
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
            monitor.MonitorContainerCleanup(mock_tm_env, {})

        res = mock_container_cleanup_action.execute(
            {
                'signal': 6,
                'id': 'mock_service',
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
    def test_execute(self):
        """Test shutting down of the container services.
        """
        apps_dir = os.path.join(self.root, 'apps')
        data_dir = os.path.join(apps_dir, 'proid.app-0000000001-abcde', 'data')
        os.makedirs(data_dir)

        mock_tm_env = mock.Mock(apps_dir=apps_dir)
        treadmill.supervisor.open_service.return_value = mock.Mock(
            data_dir=data_dir
        )

        monitor_container_down = monitor.MonitorContainerDown(mock_tm_env, {})
        res1 = monitor_container_down.execute(
            {
                'id': 'proid.app-0000000001-abcde,service1',
                'return_code': 1,
                'signal': 0,
                'timestamp': 12345.123
            }
        )
        res2 = monitor_container_down.execute(
            {
                'id': 'proid.app-0000000001-abcde,service2',
                'return_code': 256,
                'signal': 15,
                'timestamp': 12345.456
            }
        )

        self.assertEqual(res1, True)
        self.assertEqual(res2, True)
        exitinfo_file = os.path.join(data_dir, 'exitinfo')
        with io.open(exitinfo_file, 'r') as f:
            exitinfo = json.load(f)
        self.assertEqual(
            exitinfo,
            {
                'service': 'service1',
                'return_code': 1,
                'signal': 0,
                'timestamp': 12345.123
            }
        )
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
        mock_down_action = monitor.MonitorNodeDown(mock_tm_env, {})

        res = mock_down_action.execute(
            {
                'id': 'mock_service',
                'return_code': 42,
                'signal': 9,
            }
        )

        # This MonitorDownAction stops the monitor.
        self.assertEqual(res, False)
        self.assertTrue(
            os.path.exists(os.path.join(self.root, 'Monitor-mock_service'))
        )


if __name__ == '__main__':
    unittest.main()
