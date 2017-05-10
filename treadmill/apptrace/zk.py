"""Watch for application state transitions."""


import fnmatch
import logging
import tempfile
import os
import sqlite3
import zlib

from treadmill import exc
from treadmill import zknamespace as z
from treadmill import zkutils

from . import events as traceevents

_LOGGER = logging.getLogger(__name__)


class AppTrace(object):
    """Trace application lifecycle events.

    Application events are stored under app task Zookeeper directory, sequence
    node for each event.

    events are in the form:
    timestamp,source,event,msg
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
        children_watch_created = self.zk.handler.event_object()
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

        # Setup the instance ID's task watch
        task_node = z.path.task(self.instanceid)

        @self.zk.DataWatch(task_node)
        @exc.exit_on_unhandled
        def _watch_task(data, stat, event):
            """Watch for task to appear and then process events.
            """
            if data is None and stat is None:
                # Node doesn't exist yet.
                _LOGGER.info('Task znode not exist %r', task_node)
                return True

            elif event and event.type == 'DELETED':
                # If task node is deleted, this is fatal, and we should exit.
                _LOGGER.warning('Task znode deleted %r', task_node)
                self._is_done.set()
                return False

            else:
                if not children_watch_created.is_set():
                    children_watch_created.set()
                    # Setup the instance ID's task node children events

                    @self.zk.ChildrenWatch(task_node)
                    @exc.exit_on_unhandled
                    def _watch_task_events(event_nodes):
                        """Process new children events."""
                        self._process_events(event_nodes, ctx)
                        return not snapshot

                return not snapshot

    def wait(self, timeout=None):
        """Wait for app lifecycle to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        return self._is_done.wait(timeout=timeout)

    def _process_events(self, event_nodes, ctx):
        """Process task event nodes.
        """
        all_events = sorted([tuple(event_node.split(','))
                             for event_node in event_nodes])

        for timestamp, source, event_type, event_data in all_events:
            if float(timestamp) <= float(self._last_event):
                continue

            self._process_event(timestamp, source, event_type, event_data, ctx)
            self._last_event = timestamp

    def _process_event(self, timestamp, source, event_type, event_data, ctx):
        """Process event of given type."""
        # Master events.
        event = traceevents.AppTraceEvent.from_data(
            timestamp=timestamp,
            source=source,
            instanceid=self.instanceid,
            event_type=event_type,
            event_data=event_data,
        )
        if event is not None:
            self._callback.process(event, ctx)


def list_history(zkclient, app_pattern):
    """List all historical tasks for given app name."""
    tasks = []
    for app in zkclient.get_children(z.TASKS):
        if fnmatch.fnmatch(app, app_pattern):
            instances = zkclient.get_children(z.path.task(app))
            tasks.extend([app + '#' + instance for instance in instances])

    return tasks


class TaskDB(object):
    """Create task DB snapshots and upload to ZK."""

    _CREATE_TASKS_TABLE = """
    create table tasks (path text, timestamp integer, data text)
    """

    _INSERT_TASK = 'insert into tasks values(?, ?, ?)'

    _SNAPSHOT_SIZE = 10000  # Approx number of rows in one snapshot.

    def __init__(self, zkclient):
        self.zkclient = zkclient
        self.name = None
        self.conn = None
        self.cur = None
        self.rows_count = 0

    def _open(self):
        """Create empty database and open connection."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            pass

        self.name = f.name
        self.conn = sqlite3.connect(f.name)
        self.cur = self.conn.cursor()
        self.cur.execute(self._CREATE_TASKS_TABLE)
        self.rows_count = 0

        _LOGGER.info('Initialized task_db snapshot: %s', self.name)

    def _close(self):
        """Close database, compress and upload to ZK."""
        _LOGGER.info('Closing task_db snapshot: %s, total rows: %s',
                     self.name, self.rows_count)
        self.conn.commit()
        self.conn.close()

        if self.rows_count > 0:
            db_node_path = z.path.tasks_history('tasks.db.gzip-')
            with open(self.name, 'rb') as f:
                db_node = zkutils.create(
                    self.zkclient, db_node_path, zlib.compress(
                        f.read()
                    ),
                    sequence=True
                )
                _LOGGER.info('Uploaded compressed task_db snapshot: %s to: %s',
                             self.name, db_node)

        os.unlink(self.name)
        self.name = None
        self.conn = None
        self.cur = None
        self.rows_count = 0

    def add(self, rows, close=False):
        """Add rows to the database as transaction, upload when enough rows."""
        if not self.conn:
            self._open()

        _LOGGER.info('task_db: added %s rows to: %s', len(rows), self.name)
        self.cur.executemany(self._INSERT_TASK, rows)
        self.rows_count += len(rows)
        self.conn.commit()

        if close or self.rows_count > self._SNAPSHOT_SIZE:
            self._close()
            return True
        else:
            return False


def _delete_all(zkclient, to_be_deleted, recursive=True):
    """Delete a list of paths."""
    for path in to_be_deleted:
        _LOGGER.info('Removing: %s (cleanup)', path)
        zkutils.ensure_deleted(zkclient, path, recursive)


def _cleanup_tasks(zkclient):
    """Move finished tasks (with trace) to tasks history.

    Tasks history is chunked into a compressed sqlite snapshots of about 200KB.
    """
    task_db = TaskDB(zkclient)

    rows = []
    to_be_deleted = []

    tasks = zkclient.get_children(z.TASKS)
    for task in tasks:
        instances = sorted(zkclient.get_children(z.path.task(task)))
        fullnames = ['%s#%s' % (task, instance) for instance in instances]
        finished = [fullname for fullname in fullnames
                    if not zkclient.exists(z.path.scheduled(fullname))]

        for fullname in finished:
            # Archive instance data, it's a summary info used by the state API.
            data, stat = zkclient.get(z.path.task(fullname))
            timestamp = int(stat.last_modified)
            rows.append((z.path.task(fullname), timestamp, data))

            # Archive instance trace, parse timestamp from event (as in zk2fs).
            events = zkclient.get_children(z.path.task(fullname))
            for event in events:
                when, _rest = event.split(',', 1)
                timestamp = int(float(when))
                rows.append((z.path.task(fullname, event), timestamp, None))

            # Commit after 1k rows, upload after 10k rows, delete data from ZK.
            to_be_deleted.append(z.path.task(fullname))
            if len(rows) > 1000:
                uploaded = task_db.add(rows)
                rows = []
                if uploaded:
                    _delete_all(zkclient, to_be_deleted)
                    to_be_deleted = []

    # Add remaining rows.
    task_db.add(rows, close=True)
    _delete_all(zkclient, to_be_deleted)


_MAX_TASKS_HISTORY_SIZE = 1000  # Max number of snapshots.


def _cleanup_tasks_history(zkclient):
    """Delete old tasks history, keep last MAX_TASKS_HISTORY_SIZE snapshots."""
    tasks_history = sorted(zkclient.get_children(z.TASKS_HISTORY))

    to_be_deleted = [
        z.path.tasks_history(old_tasks_history)
        for old_tasks_history in tasks_history[:-_MAX_TASKS_HISTORY_SIZE]
    ]

    _delete_all(zkclient, to_be_deleted, recursive=False)


def cleanup(zkclient):
    """Run single gc cycle."""
    _cleanup_tasks(zkclient)
    _cleanup_tasks_history(zkclient)
