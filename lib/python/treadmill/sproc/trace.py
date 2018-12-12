"""Cleans up old trace from Treadmill."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils

from treadmill.trace.app import zk as app_zk
from treadmill.trace.server import zk as server_zk


_LOGGER = logging.getLogger(__name__)

# Interval between cleanup - every min
TRACE_CLEANUP_INTERVAL = 60

# Default max trace evictions count.
TRACE_EVICTIONS_MAX_COUNT = 10

# Default max trace service events count.
TRACE_SERVICE_EVENTS_MAX_COUNT = 10

# Number of traces in batch.
TRACE_BATCH = 5000

# Default trace expiration - 5min.
TRACE_EXPIRE_AFTER = 5 * 60

# Number of traces in batch.
FINISHED_BATCH = 5000

# Default trace expiration - 5min.
FINISHED_EXPIRE_AFTER = 5 * 60

# Default msx finished history count.
FINISHED_HISTORY_MAX_COUNT = 100

# Default max trace history count.
TRACE_HISTORY_MAX_COUNT = 100


def init():
    """Top level command handler."""

    @click.group()
    def trace():
        """Manage Treadmill traces.
        """

    @trace.command()
    @click.option('--interval', help='Timeout between checks (sec).',
                  default=TRACE_CLEANUP_INTERVAL)
    @click.option('--trace-evictions-max-count',
                  help='Max trace evictions count.',
                  type=int, default=TRACE_EVICTIONS_MAX_COUNT)
    @click.option('--trace-service-events-max-count',
                  help='Max trace service events count.',
                  type=int, default=TRACE_SERVICE_EVENTS_MAX_COUNT)
    @click.option('--trace-batch-size', help='Batch size.',
                  type=int, default=TRACE_BATCH)
    @click.option('--trace-expire-after', help='Expire after (sec).',
                  type=int, default=TRACE_EXPIRE_AFTER)
    @click.option('--trace-history-max-count',
                  help='Max trace history to keep.',
                  type=int, default=TRACE_HISTORY_MAX_COUNT)
    @click.option('--finished-batch-size', help='Batch size.',
                  type=int, default=FINISHED_BATCH)
    @click.option('--finished-expire-after', help='Expire after (sec).',
                  type=int, default=FINISHED_EXPIRE_AFTER)
    @click.option('--finished-history-max-count',
                  help='Max finished history to keep.',
                  type=int, default=FINISHED_HISTORY_MAX_COUNT)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def cleanup(interval,
                trace_evictions_max_count,
                trace_service_events_max_count,
                trace_batch_size,
                trace_expire_after,
                trace_history_max_count,
                finished_batch_size,
                finished_expire_after,
                finished_history_max_count,
                no_lock):
        """Cleans up old traces."""

        def _cleanup():
            """Do cleanup."""
            while True:
                app_zk.prune_trace_evictions(
                    context.GLOBAL.zk.conn,
                    trace_evictions_max_count
                )
                app_zk.prune_trace_service_events(
                    context.GLOBAL.zk.conn,
                    trace_service_events_max_count
                )
                app_zk.cleanup_trace(
                    context.GLOBAL.zk.conn,
                    trace_batch_size,
                    trace_expire_after
                )
                app_zk.cleanup_finished(
                    context.GLOBAL.zk.conn,
                    finished_batch_size,
                    finished_expire_after
                )
                app_zk.cleanup_trace_history(
                    context.GLOBAL.zk.conn,
                    trace_history_max_count
                )
                app_zk.cleanup_finished_history(
                    context.GLOBAL.zk.conn,
                    finished_history_max_count
                )

                server_zk.cleanup_server_trace(
                    context.GLOBAL.zk.conn,
                    trace_batch_size
                )
                server_zk.cleanup_server_trace_history(
                    context.GLOBAL.zk.conn,
                    trace_history_max_count
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
