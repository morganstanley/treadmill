"""Treadmill version monitor.

The monitor will watch a /version/<hostname> Zookeeper node.

If the node is deleted, it will run an "upgrade/reset" script, and recreated
the node.

The content of the node contain real path of the Treadmill code and timestamp
when the reset happened.
"""
from __future__ import absolute_import

import logging
import os
import subprocess
import time

import click

from .. import appmgr
from .. import context
from .. import exc
from .. import subproc
from .. import sysinfo
from .. import utils
from .. import versionmgr
from .. import watchdog
from .. import zkutils


def init():
    """Top level command handler."""

    # TODO: main is too long, need to be refactored.
    #
    # pylint: disable=R0915
    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('command', nargs=-1)
    def version_monitor(approot, command):
        """Runs node version monitor."""
        cli_cmd = list(command)
        logging.info('Initializing code monitor: %r', cli_cmd)

        watchdogs = watchdog.Watchdog(
            os.path.join(
                approot,
                appmgr.AppEnvironment.WATCHDOG_DIR,
            )
        )

        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        while not context.GLOBAL.zk.conn.exists(zkutils.VERSION):
            logging.warn('%r node not created yet. Cell masters running?',
                         zkutils.VERSION)
            time.sleep(30)

        hostname = sysinfo.hostname()
        version_path = os.path.join(zkutils.VERSION, hostname)

        codepath = os.path.realpath(utils.rootdir())
        digest = versionmgr.checksum_dir(codepath).hexdigest()
        logging.info('codepath: %s, digest: %s', codepath, digest)

        info = {
            'codepath': codepath,
            'since': int(time.time()),
            'digest': digest,
        }

        zkutils.put(context.GLOBAL.zk.conn, version_path, info)

        @context.GLOBAL.zk.conn.DataWatch(version_path)
        @exc.exit_on_unhandled
        def _watch_version(_data, _stat, event):
            """Force exit if server node is deleted."""

            # If the node is deleted, we exit to pick up new version code.
            if event is not None and event.type == 'DELETED':
                # The version info not present, restart services and register
                # new checksum.
                logging.info('Upgrade requested, running: %s', cli_cmd)

                if cli_cmd:
                    try:
                        subproc.check_call(cli_cmd)
                        # Record successful upgrade.
                    except subprocess.CalledProcessError:
                        logging.exception('Upgrade failed.')
                        # Immediately trigger a watchdog timeout
                        watchdogs.create(
                            name='version_monitor',
                            timeout='0s',
                            content='Upgrade to '
                                    '{code!r}({digest}) failed'.format(
                                        code=codepath,
                                        digest=digest),
                        ).heartbeat()
                        del info['digest']

                logging.info('Upgrade complete.')
                utils.sys_exit(0)

            return True

        while True:
            time.sleep(100000)

        logging.info('service shutdown.')

    return version_monitor
