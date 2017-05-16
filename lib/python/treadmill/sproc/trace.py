"""Cleans up old trace from Treadmill."""
from __future__ import absolute_import

import logging
import time

import click

from treadmill.apptrace import zk
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

# Interval between cleanup - every min
TRACE_CLEANUP_INTERVAL = 60

# Number of traces in batch.
TRACE_BATCH = 5000

# Default trace expiration - 5min.
TRACE_EXPIRE_AFTER = 5 * 60

# Number of traces in batch.
FINISHED_BATCH = 5000

# Default trace expiration - 5min.
FINISHED_EXPIRE_AFTER = 5 * 60


def init():
    """Top level command handler."""

    @click.group()
    def trace():
        """Manage Treadmill traces."""
        pass

    @trace.command()
    @click.option('--interval', help='Timeout between checks (sec).',
                  default=TRACE_CLEANUP_INTERVAL)
    @click.option('--trace-batch-size', help='Batch size.',
                  type=int, default=TRACE_BATCH)
    @click.option('--trace-expire-after', help='Expire after (sec).',
                  type=int, default=TRACE_EXPIRE_AFTER)
    @click.option('--finished-batch-size', help='Batch size.',
                  type=int, default=FINISHED_BATCH)
    @click.option('--finished-expire-after', help='Expire after (sec).',
                  type=int, default=FINISHED_EXPIRE_AFTER)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def cleanup(interval, trace_batch_size, trace_expire_after,
                finished_batch_size, finished_expire_after, no_lock):
        """Cleans up old traces."""

        def _cleanup():
            """Do cleanup."""
            while True:
                zk.cleanup_trace(
                    context.GLOBAL.zk.conn,
                    trace_batch_size,
                    trace_expire_after
                )
                zk.cleanup_finished(
                    context.GLOBAL.zk.conn,
                    finished_batch_size,
                    finished_expire_after
                )
                _LOGGER.info('Finished cleanup, sleep %s sec', interval)
                time.sleep(interval)

        if no_lock:
            _cleanup()
        else:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))
            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _cleanup()

    del cleanup
    return trace
