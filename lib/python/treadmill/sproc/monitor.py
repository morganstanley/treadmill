"""Treadmill service policy monitor."""

from __future__ import absolute_import

import logging
import click

from treadmill import appenv
from treadmill import monitor


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.group(name='svc-monitor')
    def svc_monitor_grp():
        """Monitor group of services."""
        pass

    @svc_monitor_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('-s', '--service-dir', type=click.Path(exists=True),
                  help='Services directory.', multiple=True)
    def node_services(approot, service_dir):
        """Setup a node services monitor enforcing restart policies.
        """
        tm_env = appenv.AppEnvironment(root=approot)
        down_action = monitor.MonitorNodeDown(tm_env)
        mon = monitor.Monitor(
            services_dir=None,
            service_dirs=service_dir,
            policy_impl=monitor.MonitorRestartPolicy,
            down_action=down_action
        )
        mon.run()

    del node_services
    return svc_monitor_grp
