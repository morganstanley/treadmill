"""Process alerts.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import os.path

import click

from treadmill import alert
from treadmill import appenv
from treadmill import dirwatch
from treadmill import fs

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_DEF_WAITING_PERIOD = 120
_DEF_MAX_QUEUE_LEN = 100


class _NoOpBackend:
    """Dummy default alert backend if no plugin can be found.
    """
    @staticmethod
    def send_event(type_=None,
                   instanceid=None,
                   summary=None,
                   event_time=None,
                   on_success_callback=None,
                   **kwargs):
        """Log the alert in params.
        """
        # pylint: disable=unused-argument

        _LOGGER.critical(
            'Alert raised: %s:%s:\n %s %s', type_, instanceid, summary, kwargs
        )
        if on_success_callback is not None:
            on_success_callback()


def _get_on_create_handler(alert_backend):
    """Return a func using 'alert_backend' to handle if an alert is created.
    """

    def _on_created(alert_file):
        """Handler for newly created alerts.
        """

        # Avoid triggerring on temporary files
        if os.path.basename(alert_file)[0] == '.':
            return None

        try:
            alert_ = alert.read(alert_file)
        except OSError as err:
            if err.errno == errno.ENOENT:
                # File already gone, nothing to do.
                return None
            else:
                raise

        return alert_backend.send_event(
            on_success_callback=lambda: fs.rm_safe(alert_file),
            **alert_
        )

    return _on_created


def _load_alert_backend(plugin_name):
    backend = _NoOpBackend()

    if plugin_name is None:
        return backend

    try:
        backend = plugin_manager.load('treadmill.alert.plugins', plugin_name)
    except KeyError:
        _LOGGER.info('Alert backend %r could not been loaded.', plugin_name)

    return backend


def _serve_forever(watcher, alerts_dir, max_queue_length, wait_interval):
    """Wait for and handle events until the end of time.
    """
    while True:
        _process_existing_alerts(alerts_dir, watcher.on_created)

        if watcher.wait_for_events(timeout=wait_interval):
            watcher.process_events()

        _remove_extra_alerts(alerts_dir, max_queue_length)


def _process_existing_alerts(alerts_dir, process_func):
    """Retry sending the alerts in alerts_dir.
    """
    for alert_file in os.listdir(alerts_dir):
        process_func(os.path.join(alerts_dir, alert_file))


def _remove_extra_alerts(alerts_dir, max_queue_length):
    """Keep the most recent max_queue_length files in alerts_dir.
    """
    for alert_file in sorted(os.listdir(alerts_dir))[:-1 * max_queue_length]:
        fs.rm_safe(os.path.join(alerts_dir, alert_file))


def init():
    """App main.
    """

    @click.command(name='alert_monitor')
    @click.option(
        '--approot',
        type=click.Path(exists=True),
        envvar='TREADMILL_APPROOT',
        required=True
    )
    @click.option('--plugin', help='Alert backend to use', required=False)
    @click.option(
        '--max-queue-length',
        help='Keep at most that many files in alerts directory'
        ', default: {}'.format(_DEF_MAX_QUEUE_LEN),
        type=int,
        default=_DEF_MAX_QUEUE_LEN
    )
    @click.option(
        '--wait-interval',
        help='Time to wait between WT alerting retry attempts (sec)'
        ', default: {}'.format(_DEF_WAITING_PERIOD),
        type=int,
        default=_DEF_WAITING_PERIOD
    )
    def alert_monitor_cmd(approot, plugin, max_queue_length, wait_interval):
        """Publish alerts.
        """
        tm_env = appenv.AppEnvironment(root=approot)
        watcher = dirwatch.DirWatcher(tm_env.alerts_dir)
        watcher.on_created = _get_on_create_handler(
            _load_alert_backend(plugin)
        )

        _serve_forever(
            watcher, tm_env.alerts_dir, max_queue_length, wait_interval
        )

    return alert_monitor_cmd
