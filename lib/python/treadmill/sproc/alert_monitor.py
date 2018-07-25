"""Process alerts."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import os.path
import logging

import click

from treadmill import alert
from treadmill import appenv
from treadmill import dirwatch
from treadmill import fs

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)


class _NoOpBackend:
    """Dummy default alert backend if no plugin can be found."""

    # W0613: unused argument ...
    # pylint: disable=W0613
    @staticmethod
    def send_event(
            type_=None,
            instanceid=None,
            summary=None,
            event_time=None,
            on_success_callback=None,
            **kwargs
    ):
        """Log the alert in params."""
        _LOGGER.critical(
            'Alert raised: %s:%s:\n %s %s', type_, instanceid, summary, kwargs
        )
        on_success_callback()


def _get_on_create_handler(alert_backend):
    """Return a func using 'alert_backend' to handle if an alert is created."""

    def _on_created(alert_file):
        """Handler for newly created alerts."""

        # Avoid triggerring on temporary files
        if os.path.basename(alert_file)[0] == '.':
            return None

        def _delete_alert_file():
            fs.rm_safe(alert_file)

        alert_ = alert.read(alert_file)
        return alert_backend.send_event(
            on_success_callback=_delete_alert_file, **alert_
        )

    return _on_created


def _load_alert_backend(plugin_name):
    backend = _NoOpBackend()

    if plugin_name is None:
        return backend

    try:
        backend = plugin_manager.load('treadmill.alert.plugins', plugin_name)
    except KeyError:
        _LOGGER.info(
            '''Alert backend '%s' could not been loaded.''', plugin_name
        )

    return backend


def _serve_forever(watcher):
    """Wait for and handle events until the end of time."""
    while True:
        if watcher.wait_for_events():
            watcher.process_events()


def init():
    """App main."""

    @click.command(name='alert_monitor')
    @click.option(
        '--approot',
        type=click.Path(exists=True),
        envvar='TREADMILL_APPROOT',
        required=True
    )
    @click.option('--plugin', help='Alert backend to use', required=False)
    def alert_monitor_cmd(approot, plugin):
        """Publish alerts."""
        tm_env = appenv.AppEnvironment(root=approot)
        watcher = dirwatch.DirWatcher(tm_env.alerts_dir)
        watcher.on_created = _get_on_create_handler(
            _load_alert_backend(plugin)
        )

        # if there are alerts in alerts_dir already
        for alert_file in os.listdir(tm_env.alerts_dir):
            watcher.on_created(os.path.join(tm_env.alerts_dir, alert_file))

        _serve_forever(watcher)

    return alert_monitor_cmd
