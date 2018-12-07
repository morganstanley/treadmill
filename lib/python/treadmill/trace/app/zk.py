"""Manage app trace in ZK.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import fnmatch
import logging
import os
import sqlite3
import tempfile
import time
import zlib

import kazoo

from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

from . import events as traceevents
from .. import _zk

_LOGGER = logging.getLogger(__name__)

_HOSTNAME = sysinfo.hostname()

TRACE_SOW_DIR = os.path.join('.sow', 'trace')
TRACE_SOW_TABLE = 'trace'


def publish(zkclient, when, instanceid, event_type, event_data, payload):
    """Publish application event to ZK.
    """
    eventnode = '%s,%s,%s,%s' % (when, _HOSTNAME, event_type, event_data)
    _LOGGER.debug('Creating %s', z.path.trace(instanceid, eventnode))

    acl = zkclient.make_servers_acl()
    try:
        zkutils.with_retry(
            zkutils.create,
            zkclient,
            z.path.trace(instanceid, eventnode),
            payload,
            acl=[acl]
        )
    except kazoo.client.NodeExistsError:
        pass

    if event_type in ['aborted', 'killed', 'finished']:
        # For terminal state, update the finished node with exit summary.
        zkutils.with_retry(
            zkutils.put,
            zkclient,
            z.path.finished(instanceid),
            {'state': event_type,
             'when': when,
             'host': _HOSTNAME,
             'data': event_data},
            acl=[acl],
        )

        _unschedule(zkclient, instanceid)


def _unschedule(zkclient, instanceid):
    """Safely delete scheduled node."""
    scheduled_node = z.path.scheduled(instanceid)

    # Check placement node. Only delete scheduled app if it is currently
    # placed on the server.
    #
    # If we are processing stale events, app can be placed elsewhere, and in
    # this case this server does not own placement and should not delete
    # scheduled node.
    placement_node = z.path.placement(_HOSTNAME, instanceid)

    if zkclient.exists(placement_node):
        _LOGGER.info('Unscheduling: %s', scheduled_node)
        zkutils.with_retry(
            zkutils.ensure_deleted, zkclient,
            scheduled_node
        )
    else:
        _LOGGER.info('Stale event, placement does not exist: %s',
                     placement_node)


class AppTraceLoop(_zk.TraceLoop):
    """App trace loop.
    """

    def run(self, snapshot=False, ctx=None):
        """Run event loop.
        """
        if snapshot:
            self._is_done.set()

        scheduled_node = z.path.scheduled(self._object_name)

        # Setup the instance ID's scheduled status watch
        @self._zkclient.DataWatch(scheduled_node)
        @utils.exit_on_unhandled
        def _watch_scheduled(data, stat, event):
            """Called when app scheduled node is modified.
            """
            if data is None and stat is None:
                # Node does not exist yet (or already gone).
                self._is_done.set()
                return False

            elif event and event.type == 'DELETED':
                # Node is deleted.
                self._is_done.set()
                return False

            else:
                return not snapshot

        if not self._zkclient.exists(scheduled_node):
            self._process_db_events(ctx)

        trace_node = z.path.trace(self._object_name)

        try:
            @self._zkclient.ChildrenWatch(trace_node)
            @utils.exit_on_unhandled
            def _watch_trace_events(event_nodes):
                """Process new children events.
                """
                self._process_events(event_nodes, ctx)
                return not snapshot
        except kazoo.client.NoNodeError:
            _LOGGER.warning('Trace does not exist: %s', self._object_name)
            self._is_done.set()
            return

    def _process_db_events(self, ctx):
        """Process events from trace db snapshots.
        """
        for node in self._zkclient.get_children(z.TRACE_HISTORY):
            node_path = z.path.trace_history(node)
            _LOGGER.debug('Checking trace db snapshot: %s', node_path)
            events = _zk.download_batch(
                self._zkclient,
                node_path,
                TRACE_SOW_TABLE,
                name=self._object_name
            )
            self._process_events(events, ctx)

    def _process_event(self, object_name, timestamp, source, event_type,
                       event_data, ctx):
        """Process event of given type.
        """
        event = traceevents.AppTraceEvent.from_data(
            timestamp=timestamp,
            source=source,
            instanceid=object_name,
            event_type=event_type,
            event_data=event_data,
        )
        if event is not None:
            self._event_handler.process(event, ctx)


def list_traces(zkclient, app_pattern):
    """List all available traces for given app name.
    """
    if '#' not in app_pattern:
        app_pattern += '#*'

    apps = set()

    for app in zkclient.get_children(z.SCHEDULED):
        if fnmatch.fnmatch(app, app_pattern):
            apps.add(app)

    for app in zkclient.get_children(z.FINISHED):
        if fnmatch.fnmatch(app, app_pattern):
            apps.add(app)

    for node in zkclient.get_children(z.FINISHED_HISTORY):
        node_path = z.path.finished_history(node)
        _LOGGER.debug('Checking finished db snapshot: %s', node_path)

        data, _metadata = zkclient.get(node_path)
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
            f.write(zlib.decompress(data))

        conn = sqlite3.connect(f.name)
        # Before Python 3.7 parametrized GLOB pattern won't use index.
        select_stmt = """
            SELECT name FROM finished WHERE name GLOB '{app_pattern}'
        """.format(app_pattern=app_pattern)
        for row in conn.execute(select_stmt):
            apps.add(row[0])
        conn.close()

        os.unlink(f.name)

    return sorted(apps)


def prune_trace_evictions(zkclient, max_count):
    """Cleanup excessive trace events caused by evictions.
    """
    assert max_count > 0
    shards = zkclient.get_children(z.TRACE)
    for shard in shards:
        evictions = collections.Counter()
        events = zkclient.get_children(z.path.trace_shard(shard))
        for event in sorted(events, reverse=True):
            instanceid, ts, src, event_type, event_data = event.split(',')

            event_obj = traceevents.AppTraceEvent.from_data(
                timestamp=ts,
                source=src,
                instanceid=instanceid,
                event_type=event_type,
                event_data=event_data,
            )
            if not event_obj:
                continue

            # Leave pending/created events.
            if event_type == 'pending' and 'created' in event_obj.why:
                continue

            # Prune when number of evictions for an instance reached max_count.
            if evictions.get(instanceid, 0) >= max_count:
                path = z.join_zookeeper_path(z.TRACE, shard, event)
                _LOGGER.info('Pruning trace: %s', path)
                zkutils.with_retry(zkutils.ensure_deleted, zkclient, path)
            else:
                if ((event_type in ['pending', 'scheduled'] and
                     event_obj.why == 'evicted')):
                    evictions[instanceid] += 1


def prune_trace_service_events(zkclient, max_count):
    """Cleanup excessive trace events caused by services running and exiting.
    """
    assert max_count > 0
    shards = zkclient.get_children(z.TRACE)
    for shard in shards:
        service_events = collections.Counter()
        events = zkclient.get_children(z.path.trace_shard(shard))
        for event in sorted(events, reverse=True):
            instanceid, ts, src, event_type, event_data = event.split(',')

            if event_type not in ('service_running', 'service_exited'):
                continue

            service_event = traceevents.AppTraceEvent.from_data(
                timestamp=ts,
                source=src,
                instanceid=instanceid,
                event_type=event_type,
                event_data=event_data,
            )
            if not service_event:
                continue

            uniqueid, service = service_event.uniqueid, service_event.service
            service_events[(instanceid, uniqueid, service)] += 1
            if service_events[(instanceid, uniqueid, service)] > max_count:
                path = z.join_zookeeper_path(z.TRACE, shard, event)
                _LOGGER.info('Pruning trace: %s', path)
                zkutils.with_retry(zkutils.ensure_deleted, zkclient, path)


def cleanup_trace(zkclient, batch_size, expires_after):
    """Move expired traces into history folder, compressed as sqlite db.
    """
    scheduled = zkclient.get_children(z.SCHEDULED)
    shards = zkclient.get_children(z.TRACE)
    traces = []
    num_events = 0
    for shard in shards:
        events = zkclient.get_children(z.path.trace_shard(shard))
        num_events += len(events)
        for event in events:
            instanceid, timestamp, _ = event.split(',', 2)
            timestamp = float(timestamp)
            if ((instanceid not in scheduled and
                 timestamp < time.time() - expires_after)):
                traces.append((timestamp, shard, event))

    # Sort traces from older to latest.
    traces.sort()

    uploaded_events = 0
    for idx in range(0, len(traces), batch_size):
        # Take a slice of batch_size
        batch = traces[idx:idx + batch_size]
        if len(batch) < batch_size:
            _LOGGER.info('Traces: batch = %s, total = %s, exiting.',
                         batch_size, len(batch))
            break

        db_rows = [
            (z.join_zookeeper_path(z.TRACE, shard, event), timestamp, None,
             z.join_zookeeper_path(z.TRACE, shard), event)
            for timestamp, shard, event in batch
        ]

        _zk.upload_batch(
            zkclient,
            z.path.trace_history('trace.db.gzip-'),
            TRACE_SOW_TABLE,
            db_rows
        )

        uploaded_events += len(db_rows)

    _LOGGER.info('Cleaned up %s trace events, live events: %s',
                 uploaded_events, num_events - uploaded_events)


def cleanup_finished(zkclient, batch_size, expires_after):
    """Move expired finished events into finished history.
    """

    expired = []
    for finished in zkclient.get_children(z.FINISHED):
        node_path = z.path.finished(finished)
        data, metadata = zkclient.get(node_path)
        if data is not None:
            data = data.decode()
        if metadata.last_modified < time.time() - expires_after:
            expired.append((node_path, metadata.last_modified, data,
                            z.FINISHED, finished))

    for idx in range(0, len(expired), batch_size):
        batch = expired[idx:idx + batch_size]
        if len(batch) < batch_size:
            _LOGGER.info('Finished: batch = %s, total = %s, exiting.',
                         batch_size, len(batch))
            break

        _zk.upload_batch(
            zkclient,
            z.path.finished_history('finished.db.gzip-'),
            'finished',
            batch
        )


def cleanup_trace_history(zkclient, max_count):
    """Cleanup trace history.
    """
    _zk.cleanup(zkclient, z.TRACE_HISTORY, max_count)


def cleanup_finished_history(zkclient, max_count):
    """Cleanup trace history.
    """
    _zk.cleanup(zkclient, z.FINISHED_HISTORY, max_count)
