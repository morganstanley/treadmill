"""Watch for application state transitions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import fnmatch
import io
import logging
import os
import sqlite3
import tempfile
import time
import zlib

import kazoo

from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

from . import events as traceevents

_LOGGER = logging.getLogger(__name__)


class AppTrace(object):
    """Trace application lifecycle events.

    Application events are stored under app trace Zookeeper directory.

    events are in the form:
    instancename,timestamp,source,event,msg
    """
    def __init__(self, zkclient, instanceid, callback=None):
        self.zk = zkclient
        self.instanceid = instanceid
        self._last_event = None
        self._is_done = zkclient.handler.event_object()
        self._callback = callback

    def run(self, snapshot=False, ctx=None):
        """Process application events.
        """
        if snapshot:
            self._is_done.set()

        scheduled_node = z.path.scheduled(self.instanceid)

        # Setup the instance ID's scheduled status watch
        @self.zk.DataWatch(scheduled_node)
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

        if not self.zk.exists(scheduled_node):
            self._process_db_events(ctx)

        trace_node = z.path.trace(self.instanceid)

        try:
            @self.zk.ChildrenWatch(trace_node)
            @utils.exit_on_unhandled
            def _watch_trace_events(event_nodes):
                """Process new children events.
                """
                self._process_events(event_nodes, ctx)
                return not snapshot
        except kazoo.client.NoNodeError:
            _LOGGER.warning('Trace does not exist: %s', self.instanceid)
            self._is_done.set()
            return

    def wait(self, timeout=None):
        """Wait for app lifecycle to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        return self._is_done.wait(timeout=timeout)

    def _process_db_events(self, ctx):
        """Process events from trace db snapshots.
        """
        for node in self.zk.get_children(z.TRACE_HISTORY):
            node_path = z.path.trace_history(node)
            _LOGGER.debug('Checking trace db snapshot: %s', node_path)

            data, _metadata = self.zk.get(node_path)
            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                f.write(zlib.decompress(data))

            conn = sqlite3.connect(f.name)
            # Before Python 3.7 parametrized GLOB pattern won't use index.
            select_stmt = """
                SELECT name FROM trace WHERE name GLOB '{instanceid},*'
            """.format(instanceid=self.instanceid)
            events = []
            for row in conn.execute(select_stmt):
                events.append(row[0])
            self._process_events(events, ctx)
            conn.close()

            os.unlink(f.name)

    def _process_events(self, events, ctx):
        """Parse, sort, filter, deduplicate and process events.
        """
        events = sorted(tuple(event.split(',')) for event in events)

        for event in events:
            instanceid, timestamp, source, event_type, event_data = event

            if instanceid != self.instanceid:
                continue

            # Skip event if it's older than the last one or it's the same event
            if ((self._last_event and
                 (event[1] < self._last_event[1] or
                  event == self._last_event))):
                continue

            self._process_event(
                instanceid, timestamp, source, event_type, event_data, ctx
            )
            self._last_event = event

    def _process_event(self, instanceid, timestamp, source, event_type,
                       event_data, ctx):
        """Process event of given type.
        """
        # Master events.
        event = traceevents.AppTraceEvent.from_data(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            event_type=event_type,
            event_data=event_data,
        )
        if event is not None:
            self._callback.process(event, ctx)


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


def _upload_batch(zkclient, db_node_path, table, batch):
    """Generate snapshot DB and upload to zk.
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        pass

    conn = sqlite3.connect(f.name)
    with conn:
        conn.execute(
            """
            CREATE TABLE {table} (
                path text, timestamp real, data text,
                directory text, name text
            )
            """.format(table=table)
        )
        conn.executemany(
            """
            INSERT INTO {table} (
                path, timestamp, data, directory, name
            ) VALUES(?, ?, ?, ?, ?)
            """.format(table=table), batch
        )
        conn.executescript(
            """
            CREATE INDEX name_idx ON {table} (name);
            CREATE INDEX path_idx ON {table} (path);
            """.format(table=table)
        )
    conn.close()

    with io.open(f.name, 'rb') as f:
        db_node = zkutils.create(
            zkclient, db_node_path, zlib.compress(f.read()),
            sequence=True
        )
        _LOGGER.info(
            'Uploaded compressed snapshot DB: %s to: %s',
            f.name, db_node
        )

    os.unlink(f.name)

    # Delete uploaded nodes from zk.
    for path, _timestamp, _data, _directory, _name in batch:
        zkutils.with_retry(zkutils.ensure_deleted, zkclient, path)


def prune_trace(zkclient, max_count):
    """Prune trace. Cleanup service (running/exited) events.
    """
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
    for shard in shards:
        events = zkclient.get_children(z.path.trace_shard(shard))
        for event in events:
            instanceid, timestamp, _ = event.split(',', 2)
            timestamp = float(timestamp)
            if ((instanceid not in scheduled and
                 timestamp < time.time() - expires_after)):
                traces.append((timestamp, shard, event))

    # Sort traces from older to latest.
    traces.sort()

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

        _upload_batch(
            zkclient,
            z.path.trace_history('trace.db.gzip-'),
            'trace',
            db_rows
        )


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

        _upload_batch(
            zkclient,
            z.path.finished_history('finished.db.gzip-'),
            'finished',
            batch
        )


def _cleanup(zkclient, path, max_count):
    """Cleanup old nodes given path.
    """
    nodes = sorted(zkclient.get_children(path))
    extra = len(nodes) - max_count
    if extra > 0:
        for node in nodes[0:extra]:
            zkutils.ensure_deleted(zkclient,
                                   z.join_zookeeper_path(path, node))


def cleanup_trace_history(zkclient, max_count):
    """Cleanup trace history.
    """
    _cleanup(zkclient, z.TRACE_HISTORY, max_count)


def cleanup_finished_history(zkclient, max_count):
    """Cleanup trace history.
    """
    _cleanup(zkclient, z.FINISHED_HISTORY, max_count)
