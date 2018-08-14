"""Unit tests for treadmill.sproc.alert_monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import tempfile
import unittest

import click
import click.testing
import mock

from treadmill import alert
from treadmill import fs
from treadmill.sproc import alert_monitor


class AlertMonitorTest(unittest.TestCase):
    """Test treadmill.sproc.alert_monitor.
    """

    @mock.patch('treadmill.sproc.alert_monitor._LOGGER')
    def test_noopbackend(self, logger_mock):
        """Test _NoOpBackend().
        """
        # pylint: disable=protected-access

        alert_ = dict(
            type_='test',
            summary='test summary',
            instanceid='origin',
            foo='bar'
        )

        with tempfile.TemporaryDirectory() as alerts_dir:
            on_created = alert_monitor._get_on_create_handler(
                alert_monitor._load_alert_backend(None)
            )

            alert.create(alerts_dir, **alert_)
            alert_file = os.listdir(alerts_dir)[0]

            on_created(os.path.join(alerts_dir, alert_file))

            logger_mock.critical.assert_called_once_with(
                mock.ANY, alert_['type_'], alert_['instanceid'],
                alert_['summary'], {
                    'foo': 'bar',
                    'epoch_ts': mock.ANY
                }
            )

            # check that success callback is invoked and the alert is deleted
            with self.assertRaises(FileNotFoundError):
                alert.read(alert_file, alerts_dir)

    def test_load_alert_backend(self):
        """Test _load_alert_backend().
        """
        # pylint: disable=protected-access

        self.assertTrue(
            isinstance(
                alert_monitor._load_alert_backend(None),
                alert_monitor._NoOpBackend
            )
        )
        self.assertTrue(
            isinstance(
                alert_monitor._load_alert_backend('No such backend'),
                alert_monitor._NoOpBackend
            )
        )

    @mock.patch('treadmill.sproc.alert_monitor.dirwatch.DirWatcher',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.sproc.alert_monitor._serve_forever',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.sproc.alert_monitor._load_alert_backend')
    @mock.patch('treadmill.sproc.alert_monitor.appenv')
    def test_alert_monitor_cmd(self, mock_appenv, mock_load):
        """Test alert_monitor_cmd().
        """
        mock_backend = mock_load.return_value

        with tempfile.TemporaryDirectory() as dir_name:
            mock_appenv.AppEnvironment.return_value.alerts_dir = dir_name
            fs.mkfile_safe(os.path.join(dir_name, '.keepme'))
            with open(os.path.join(dir_name, 'mock_alert'), 'w') as f:
                f.write('{"type_": "mock"}')

            alert_monitor_cli = alert_monitor.init()
            run = click.testing.CliRunner().invoke(
                alert_monitor_cli, ['--approot', os.getcwd()]
            )

        self.assertEqual(run.exit_code, 0, str(run))
        mock_backend.send_event.assert_called_once_with(
            type_='mock',
            on_success_callback=mock.ANY
        )


if __name__ == '__main__':
    unittest.main()
