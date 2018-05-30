"""Treadmill reboot monitor.

The monitor will watch a /reboots/<hostname> Zookeeper node.

If the node exists, and created after server was rebooted, node will reboot.

If the node exists but is created before server was rebooted, node will be
deleted (as server was rebooted already).

Actual reboot procedure is specified in command line. Prior to invoking
the plugin, perform graceful shutdown.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import context
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

# Do not reboot if server uptime is less than 2 hours.
_MIN_UPTIME_BEFORE_REBOOT = 60 * 60 * 2


def init():
    """Top level command handler."""

    # TODO: main is too long, need to be refactored.
    #
    # pylint: disable=R0915
    @click.command()
    @click.argument('command', nargs=-1)
    def reboot_monitor(command):
        """Runs node reboot monitor."""
        reboot_cmd = list(command)
        _LOGGER.info('Initializing reboot monitor: %r', reboot_cmd)

        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_lost)

        while not zkclient.exists(z.REBOOTS):
            _LOGGER.warning('%r node not created yet. Cell masters running?',
                            z.REBOOTS)
            time.sleep(30)

        hostname = sysinfo.hostname()
        up_since = sysinfo.up_since()

        _LOGGER.info('Server: %s, up since: %s', hostname, up_since)
        reboot_path = z.path.reboot(hostname)

        reboot_trigger = zkclient.handler.event_object()
        reboot_trigger.clear()

        @zkclient.DataWatch(reboot_path)
        @utils.exit_on_unhandled
        def _watch_reboot(data, stat, event):
            """Watch reboot node."""

            if data is None and event is None:
                _LOGGER.info('Reboot node does not exist, ignore.')
                return True

            elif event is not None and event.type == 'DELETED':
                _LOGGER.info('Reboot Node deleted, ignore.')
                return True

            # We have a reboot request node
            if stat.created > up_since:
                _LOGGER.info('Reboot requested at: %s, up since: %s',
                             time.ctime(stat.created),
                             time.ctime(up_since))

                reboot_trigger.set()
            else:
                _LOGGER.info('Reboot success, requested at %s, up since: %s',
                             time.ctime(stat.created),
                             time.ctime(up_since))

                _LOGGER.info('Deleting zknode: %r', reboot_path)
                zkutils.ensure_deleted(zkclient, reboot_path)
            return True

        # We now wait for the reboot trigger
        reboot_trigger.wait()

        # Actual reboot procedure below

        _LOGGER.info('service shutdown.')
        # Strictly speaking this is not enough for graceful shutdown.
        #
        # We need a proper shutdown procedure developed.

        _LOGGER.info('Checking blackout list.')
        zk_blackout_path = z.path.blackedout_server(hostname)
        while zkclient.exists(zk_blackout_path):
            _LOGGER.info('Node blacked out - will wait.')
            time.sleep(60)

        if time.time() - up_since > _MIN_UPTIME_BEFORE_REBOOT:
            _LOGGER.info('exec: %r', reboot_cmd)
            utils.sane_execvp(reboot_cmd[0], reboot_cmd)
        else:
            _LOGGER.info('Possible reboot loop detected, blackout the node.')
            zkutils.ensure_exists(
                zkclient,
                zk_blackout_path,
                acl=[zkclient.make_host_acl(hostname, 'rwcda')],
                data='Possible reboot loop detected.'
            )

    return reboot_monitor
