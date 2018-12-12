"""Saves the scheduler state to permanent storage.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os.path
import time

from datetime import datetime

import kazoo.exceptions
import click

from twisted.internet import reactor, task

from treadmill import context
from treadmill import fs
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def export_reports(out_dir, zkclient):
    """Export scheduler reports from ZooKeeper to disk."""
    start = time.time()
    start_iso = datetime.utcfromtimestamp(int(start)).isoformat()

    try:
        reports = zkclient.get_children('/reports')
    except kazoo.exceptions.NoNodeError:
        _LOGGER.critical('Reports not found in %s ZooKeeper!',
                         context.GLOBAL.cell)
        return

    for report_type in reports:
        # Write the byte contents from ZK, reports are already compressed
        report, _ = zkclient.get(z.path.state_report(report_type))
        filename = '{}_{}.csv.bz2'.format(start_iso, report_type)
        with io.open(os.path.join(out_dir, filename), 'wb') as out:
            out.write(report)

    _LOGGER.info('State reports exported in %s (%.3f seconds)',
                 os.path.join(out_dir, '{}_*.csv.bz2'.format(start_iso)),
                 time.time() - start)


def run_reactor(out_dir, interval, zkclient):
    """Run the export loop in a Twisted reactor for proper timing."""
    loop = task.LoopingCall(
        zkutils.with_retry,
        export_reports,
        out_dir,
        zkclient
    )
    loop.start(interval)
    reactor.run()


def init():
    """Main command handler."""

    @click.command(name='export-reports')
    @click.option('-o', '--out-dir', type=click.Path(), required=False,
                  help='Path to the directory where reports will be saved')
    @click.option('-i', '--interval', type=int, required=False,
                  help='Number of seconds between iterations')
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Do not attempt to acquire an election lock')
    def run(out_dir, interval, no_lock):
        """Export scheduler reports from ZooKeeper to disk."""
        zkclient = context.GLOBAL.zk.conn
        out_dir = out_dir or '.'
        fs.mkdir_safe(out_dir, mode=0o755)

        if interval:
            if no_lock:
                run_reactor(out_dir, interval, zkclient)
            else:
                lock = zkutils.make_lock(zkclient, z.path.election(__name__))
                _LOGGER.info('Waiting for leader lock.')
                with lock:
                    run_reactor(out_dir, interval, zkclient)
        else:
            export_reports(out_dir, zkclient)

    return run
