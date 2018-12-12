"""Manage trace in ZK.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import io
import logging
import os
import sqlite3
import tempfile
import zlib

from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


class TraceLoop(abc.ABC):
    """Trace loop.
    """

    def __init__(self, zkclient, object_name, event_handler):
        self._zkclient = zkclient
        self._object_name = object_name
        self._event_handler = event_handler

        self._last_event = None
        self._is_done = zkclient.handler.event_object()

    @abc.abstractmethod
    def run(self, snapshot=False, ctx=None):
        """Run event loop.
        """

    def wait(self, timeout=None):
        """Wait for event loop to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        return self._is_done.wait(timeout=timeout)

    def _process_events(self, events, ctx):
        """Parse, sort, filter, deduplicate and process events.
        """
        events = sorted(tuple(event.split(',')) for event in events)

        for event in events:
            object_name, timestamp, source, event_type, event_data = event

            if object_name != self._object_name:
                continue

            # Skip event if it's older than the last one or it's the same event
            if ((self._last_event and
                 (event[1] < self._last_event[1] or
                  event == self._last_event))):
                continue

            self._process_event(
                object_name, timestamp, source, event_type, event_data, ctx
            )
            self._last_event = event

    @abc.abstractmethod
    def _process_event(self, object_name, timestamp, source, event_type,
                       event_data, ctx):
        """Process event of given type.
        """


def upload_batch(zkclient, db_node_path, table, batch):
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


def download_batch(zkclient, db_node_path, table, name):
    """Download snapshot DB and select matching rows.
    """
    events = []
    data, _metadata = zkclient.get(db_node_path)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
        f.write(zlib.decompress(data))

    conn = sqlite3.connect(f.name)
    # Before Python 3.7 parametrized GLOB pattern won't use index.
    select_stmt = """
        SELECT name FROM {table} WHERE name GLOB '{name},*'
    """.format(table=table, name=name)
    for row in conn.execute(select_stmt):
        events.append(row[0])
    conn.close()

    os.unlink(f.name)
    return events


def cleanup(zkclient, path, max_count):
    """Cleanup old nodes given path.
    """
    nodes = sorted(zkclient.get_children(path))
    extra = len(nodes) - max_count
    if extra > 0:
        for node in nodes[0:extra]:
            zkutils.ensure_deleted(zkclient, z.join_zookeeper_path(path, node))
