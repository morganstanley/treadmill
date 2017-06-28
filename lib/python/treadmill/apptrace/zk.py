"""Watch for application state transitions."""

from __future__ import absolute_import

import fnmatch
import logging
import tempfile
import os
import sqlite3
import zlib
import time

import kazoo

from treadmill import exc
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
        self._last_event = 0
        self._is_done = zkclient.handler.event_object()
        self._callback = callback

    def run(self, snapshot=False, ctx=None):
        """Process application events.
        """
        if snapshot:
            self._is_done.set()

        # Setup the instance ID's scheduled status watch
        @self.zk.DataWatch(z.path.scheduled(self.instanceid))
        @exc.exit_on_unhandled
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

        trace_node = z.path.trace(self.instanceid)

        try:
            @self.zk.ChildrenWatch(trace_node)
            @exc.exit_on_unhandled
            def _watch_trace_events(event_nodes):
                """Process new children events."""
                self._process_events(event_nodes, ctx)
                return not snapshot
        except kazoo.client.NoNodeError:
            _LOGGER.warn('Trace does not exist: %s', self.instanceid)
            self._is_done.set()
            return

        finished_node = z.path.finished(self.instanceid)

        @self.zk.DataWatch(finished_node)
        @exc.exit_on_unhandled
        def _watch_finished(data, stat, event):
            """Watch for finished to appear and then process events.
            """
            if data is None and stat is None:
                # Node doesn't exist yet.
                _LOGGER.info('finished znode not exist %r', finished_node)
                return True

            elif event and event.type == 'DELETED':
                # If finished node is deleted, this is fatal, and we should
                # exit.
                _LOGGER.warning('finished znode deleted %r', finished_node)
                self._is_done.set()
                return False

            else:
                return not snapshot

    def wait(self, timeout=None):
        """Wait for app lifecycle to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        return self._is_done.wait(timeout=timeout)

    def _process_events(self, event_nodes, ctx):
        """Process finished event nodes.
        """
        all_events = sorted([tuple(event_node.split(','))
                             for event_node in event_nodes])

        for (instanceid,
             timestamp,
             source,
             event_type,
             event_data) in all_events:

            if timestamp < self._last_event:
                continue

            if instanceid != self.instanceid:
                continue

            self._process_event(instanceid, timestamp, source, event_type,
                                event_data, ctx)
            self._last_event = timestamp

    def _process_event(self, instanceid, timestamp, source, event_type,
                       event_data, ctx):
        """Process event of given type."""
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
    """List all available traces for given app name."""
    if '#' not in app_pattern:
        app_pattern += '#*'

    apps = []
    for app in zkclient.get_children(z.SCHEDULED):
        if fnmatch.fnmatch(app, app_pattern):
            apps.append(app)

    for app in zkclient.get_children(z.FINISHED):
        if fnmatch.fnmatch(app, app_pattern):
            apps.append(app)

    # TODO: support finished history
    return apps


def _upload_batch(zkclient, db_node_path, dbname, batch):
    """Generate snapshot DB and upload to zk."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        pass

    with sqlite3.connect(f.name) as conn:
        conn.execute(
            'create table %s (path text, timestamp integer, data text)' % (
                dbname
            )
        )
        conn.executemany(
            'insert into %s (path, timestamp, data) values(?, ?, ?)' % (
                dbname
            ),
            batch
        )
        conn.executescript(
            """
            CREATE INDEX path_timestamp_idx on %s (path, timestamp);
            """ % dbname
        )
    conn.close()

    with open(f.name, 'rb') as f:
        db_node = zkutils.create(
            zkclient, db_node_path, zlib.compress(f.read()),
            sequence=True
        )
        _LOGGER.info(
            'Uploaded compressed trace_db snapshot: %s to: %s',
            f.name, db_node
        )

    os.unlink(f.name)

    # Delete uploaded nodes from zk.
    for path, _ts, _data in batch:
        zkutils.with_retry(zkutils.ensure_deleted, zkclient, path)


def cleanup_trace(zkclient, batch_size, expires_after):
    """Move expired traces into history folder, compressed as sqlite db."""
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

    for idx in xrange(0, len(traces), batch_size):
        # Take a slice of batch_size
        batch = traces[idx:idx + batch_size]
        if len(batch) < batch_size:
            _LOGGER.info('Traces: batch = %s, total = %s, exiting.',
                         batch_size, len(batch))
            break

        db_rows = [
            (z.join_zookeeper_path(z.TRACE, shard, event), timestamp, None)
            for timestamp, shard, event in batch
        ]

        _upload_batch(
            zkclient,
            z.path.trace_history('trace.db.gzip-'),
            'trace',
            db_rows
        )


def cleanup_finished(zkclient, batch_size, expires_after):
    """Move expired finished events into finished history."""

    expired = []
    for finished in zkclient.get_children(z.FINISHED):
        node_path = z.path.finished(finished)
        data, metadata = zkclient.get(node_path)
        if metadata.last_modified < time.time() - expires_after:
            expired.append((node_path, metadata.last_modified, data))

    for idx in xrange(0, len(expired), batch_size):
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
    """Cleanup old nodes given path."""
    nodes = sorted(zkclient.get_children(path))
    extra = len(nodes) - max_count
    if extra > 0:
        for node in nodes[0:extra]:
            zkutils.ensure_deleted(zkclient,
                                   z.join_zookeeper_path(path, node))


def cleanup_trace_history(zkclient, max_count):
    """Cleanup trace history."""
    _cleanup(zkclient, z.TRACE_HISTORY, max_count)


def cleanup_finished_history(zkclient, max_count):
    """Cleanup trace history."""
    _cleanup(zkclient, z.FINISHED_HISTORY, max_count)
