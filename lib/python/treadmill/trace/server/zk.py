"""Manage server trace in ZK.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import heapq
import logging
import os

import kazoo

from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

from . import events as traceevents
from .. import _zk


_LOGGER = logging.getLogger(__name__)

_HOSTNAME = sysinfo.hostname()

SERVER_TRACE_SOW_DIR = os.path.join('.sow', 'server_trace')
SERVER_TRACE_SOW_TABLE = 'server_trace'


def publish(zkclient, when, servername, event_type, event_data, payload):
    """Publish server event to ZK.
    """
    eventnode = '%s,%s,%s,%s' % (when, _HOSTNAME, event_type, event_data)
    _LOGGER.debug('Creating %s', z.path.server_trace(servername, eventnode))

    acl = zkclient.make_servers_acl()
    try:
        zkutils.with_retry(
            zkutils.create,
            zkclient,
            z.path.server_trace(servername, eventnode),
            payload,
            acl=[acl]
        )
    except kazoo.client.NodeExistsError:
        pass


class ServerTraceLoop(_zk.TraceLoop):
    """Server trace loop.
    """

    def run(self, snapshot=False, ctx=None):
        """Run event loop.
        """
        if snapshot:
            self._is_done.set()

        self._process_db_events(ctx)

        server_trace_node = z.path.server_trace(self._object_name)

        try:
            @self._zkclient.ChildrenWatch(server_trace_node)
            @utils.exit_on_unhandled
            def _watch_server_trace_events(event_nodes):
                """Process new children events.
                """
                self._process_events(event_nodes, ctx)
                return not snapshot
        except kazoo.client.NoNodeError:
            _LOGGER.warning('Server trace does not exist: %s',
                            self._object_name)
            self._is_done.set()
            return

    def _process_db_events(self, ctx):
        """Process events from trace db snapshots.
        """
        for node in self._zkclient.get_children(z.SERVER_TRACE_HISTORY):
            node_path = z.path.server_trace_history(node)
            _LOGGER.debug('Checking server trace db snapshot: %s', node_path)
            events = _zk.download_batch(
                self._zkclient,
                node_path,
                SERVER_TRACE_SOW_TABLE,
                name=self._object_name
            )
            self._process_events(events, ctx)

    def _process_event(self, object_name, timestamp, source, event_type,
                       event_data, ctx):
        """Process event of given type.
        """
        event = traceevents.ServerTraceEvent.from_data(
            timestamp=timestamp,
            source=source,
            servername=object_name,
            event_type=event_type,
            event_data=event_data,
        )
        if event is not None:
            self._event_handler.process(event, ctx)


def cleanup_server_trace(zkclient, batch_size):
    """Move expired traces into history folder, compressed as sqlite db.
    """
    num_events = uploaded_events = 0

    while True:
        batch = []
        num_events = 0
        shards = zkclient.get_children(z.SERVER_TRACE)
        for shard in shards:
            traces = []
            events = zkclient.get_children(z.path.server_trace_shard(shard))
            num_events += len(events)
            for event in events:
                servername, timestamp, _ = event.split(',', 2)
                timestamp = float(timestamp)
                traces.append((timestamp, shard, event))
            # Sort traces from older to latest.
            traces.sort()
            # Keep batch_size traces ordered by timestamp.
            batch = [val for val in heapq.merge(batch, traces)][:batch_size]

        if len(batch) < batch_size:
            _LOGGER.info('Traces: batch = %s, total = %s, exiting.',
                         batch_size, len(batch))
            break

        db_rows = [
            (
                z.join_zookeeper_path(z.SERVER_TRACE, shard, event),
                timestamp,
                None,
                z.join_zookeeper_path(z.SERVER_TRACE, shard),
                event
            )
            for timestamp, shard, event in batch
        ]
        _zk.upload_batch(
            zkclient,
            z.path.server_trace_history('server_trace.db.gzip-'),
            SERVER_TRACE_SOW_TABLE,
            db_rows
        )
        uploaded_events += len(db_rows)

    _LOGGER.info('Cleaned up %s server trace events, live events: %s',
                 uploaded_events, num_events)


def cleanup_server_trace_history(zkclient, max_count):
    """Cleanup server trace history.
    """
    _zk.cleanup(zkclient, z.SERVER_TRACE_HISTORY, max_count)
