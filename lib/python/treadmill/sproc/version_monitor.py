"""Treadmill version monitor.

The monitor will watch a /version/<hostname> Zookeeper node.

If the node is deleted, it will run an "upgrade/reset" script, and recreated
the node.

The content of the node contain real path of the Treadmill code and timestamp
when the reset happened.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import io
import time

import click
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import appenv
from treadmill import context
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils
from treadmill import versionmgr
from treadmill import watchdog
from treadmill import zkutils
from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)

# Number of previous version of each server to save.
_MAX_VERSIONS = 20


def _codepath():
    """Get treadmill codepath.
    """
    path = os.path.join(utils.rootdir(), 'ORIG_CODEPATH')
    try:
        with io.open(path, 'rb') as codepath_file:
            codepath = codepath_file.read()
            return os.path.dirname(codepath)
    except IOError:
        return utils.rootdir()


def _save_version(zkclient, hostname, version):
    """Save server version data to ZK.
    """
    node_path = z.path.version_history(hostname)
    versions = zkutils.get_default(zkclient, node_path)
    if not versions:
        versions = []
    versions.insert(0, version)
    zkutils.put(zkclient, node_path, versions[0:_MAX_VERSIONS])


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
        _LOGGER.info('Initializing code monitor: %r', cli_cmd)

        watchdogs = watchdog.Watchdog(
            os.path.join(
                approot,
                appenv.AppEnvironment.WATCHDOG_DIR,
            )
        )

        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        while not context.GLOBAL.zk.conn.exists(z.VERSION):
            _LOGGER.warning('%r node not created yet. Cell masters running?',
                            z.VERSION)
            time.sleep(30)

        hostname = sysinfo.hostname()
        version_path = z.path.version(hostname)

        codepath = os.path.realpath(_codepath())
        digest = versionmgr.checksum_dir(codepath).hexdigest()
        _LOGGER.info('codepath: %s, digest: %s', codepath, digest)

        info = {
            'codepath': codepath,
            'since': int(time.time()),
            'digest': digest,
        }

        zkutils.put(context.GLOBAL.zk.conn, version_path, info)
        _save_version(context.GLOBAL.zk.conn, hostname, info)

        @context.GLOBAL.zk.conn.DataWatch(version_path)
        @utils.exit_on_unhandled
        def _watch_version(_data, _stat, event):
            """Force exit if server node is deleted."""

            # If the node is deleted, we exit to pick up new version code.
            if event is not None and event.type == 'DELETED':
                # The version info not present, restart services and register
                # new checksum.
                _LOGGER.info('Upgrade requested, running: %s', cli_cmd)

                if cli_cmd:
                    try:
                        subproc.check_call(cli_cmd)
                        # Record successful upgrade.
                    except subprocess.CalledProcessError:
                        _LOGGER.exception('Upgrade failed.')
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

                _LOGGER.info('Upgrade complete.')
                utils.sys_exit(0)

            return True

        while True:
            time.sleep(100000)

        _LOGGER.info('service shutdown.')

    return version_monitor
