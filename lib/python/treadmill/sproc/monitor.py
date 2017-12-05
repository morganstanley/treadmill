"""Treadmill service policy monitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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
    @click.option('-c', '--container-dir', type=click.Path(exists=True),
                  help='Container directory.', required=True)
    @click.option('-s', '--service-dir', type=click.Path(exists=True),
                  help='Services directory.', multiple=True)
    def services(approot, container_dir, service_dir):
        """Setup a services monitor enforcing restart policies.
        """
        tm_env = appenv.AppEnvironment(root=approot)
        mon = monitor.Monitor(
            scan_dirs=None,
            service_dirs=service_dir,
            policy_impl=monitor.MonitorRestartPolicy,
            down_action=monitor.MonitorContainerDown(container_dir),
            event_hook=monitor.PresenceMonitorEventHook(tm_env)
        )
        mon.run()

    @svc_monitor_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('-S', '--scan-dir', type=click.Path(exists=True),
                  help='Scan directories.', multiple=True)
    def node_services(approot, scan_dir):
        """Setup a node services monitor enforcing restart policies.
        """
        tm_env = appenv.AppEnvironment(root=approot)
        mon = monitor.Monitor(
            scan_dirs=scan_dir,
            service_dirs=None,
            policy_impl=monitor.MonitorRestartPolicy,
            down_action=monitor.MonitorNodeDown(tm_env)
        )
        mon.run()

    @svc_monitor_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('-S', '--scan-dir', type=click.Path(exists=True),
                  help='Containers directory.')
    def containers(approot, scan_dir):
        """Setup a monitor for the running containers.
        """
        tm_env = appenv.AppEnvironment(root=approot)
        mon = monitor.Monitor(
            scan_dirs=scan_dir,
            service_dirs=None,
            policy_impl=monitor.MonitorRestartPolicy,
            down_action=monitor.MonitorContainerCleanup(tm_env)
        )
        mon.run()

    @svc_monitor_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('-S', '--scan-dir', type=click.Path(exists=True),
                  help='Cleaning directory.')
    def cleaning(approot, scan_dir):
        """Setup a monitor for the running containers.
        """
        tm_env = appenv.AppEnvironment(root=approot)

        def _policy_factory():
            return monitor.CleanupMonitorRestartPolicy(tm_env)

        mon = monitor.Monitor(
            scan_dirs=scan_dir,
            service_dirs=None,
            policy_impl=_policy_factory,
            down_action=monitor.MonitorNodeDown(tm_env, prefix='cleanup-')
        )
        mon.run()

    del cleaning
    del containers
    del services
    del node_services
    return svc_monitor_grp
