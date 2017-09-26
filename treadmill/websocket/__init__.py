"""Websocket API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import errno
import fnmatch
import glob
import heapq
import io
import json
import logging
import os
import sqlite3
import threading
import time

import tornado.websocket

from six.moves import urllib_parse

from treadmill import dirwatch
from treadmill import utils


_LOGGER = logging.getLogger(__name__)


def make_handler(pubsub):
    """Make websocket handler factory."""

    class _WS(tornado.websocket.WebSocketHandler):
        """Base class contructor"""

        def __init__(self, application, request, **kwargs):
            """Default constructor for tornado.websocket.WebSocketHandler"""
            tornado.websocket.WebSocketHandler.__init__(
                self, application, request, **kwargs
            )

        def active(self):
            """Returns true if connection is active, false otherwise."""
            return bool(self.ws_connection)

        def open(self):
            """Called when connection is opened.

            Override if you want to do something else besides log the action.
            """
            _LOGGER.info('Connection opened.')

        def send_error_msg(self, error_str, close_conn=True):
            """Convenience method for logging and returning errors.

            Note: this method will close the connection after sending back the
            error, unless close_conn=False
            """
            _LOGGER.info(error_str)
            error_msg = {'_error': error_str,
                         'when': time.time()}

            self.write_message(error_msg)
            if close_conn:
                _LOGGER.info('Closing connection.')
                self.close()

        def on_close(self):
            """Called when connection is closed.

            Override if you want to do something else besides log the action.
            """
            _LOGGER.info('connection closed.')

        def check_origin(self, origin):
            """Overriding check_origin method from base class.

            This method returns true all the time.
            """
            parsed_origin = urllib_parse.urlparse(origin)
            _LOGGER.debug('parsed_origin: %r', parsed_origin)
            return True

        def on_message(self, jmessage):
            """Manage event subscriptions."""
            if not pubsub:
                _LOGGER.fatal('pubsub is not configured, ignore.')
                self.send_error_msg('Fatal: unexpected error', close_conn=True)

            try:
                message = json.loads(jmessage)
                topic = message['topic']
                impl = pubsub.impl.get(topic)
                if not impl:
                    self.send_error_msg('Invalid topic: %r' % topic)
                    return

                since = message.get('since', 0)
                snapshot = message.get('snapshot', False)
                for watch, pattern in impl.subscribe(message):
                    pubsub.register(watch, pattern, self, impl, since)
                if snapshot:
                    self.close()

            except Exception as err:  # pylint: disable=W0703
                self.send_error_msg(str(err))

        def data_received(self, message):
            """Passthrough of abstract method data_received"""
            pass

        def on_event(self, filename, operation, _content):
            """Default event handler."""
            _LOGGER.debug('%s %s', filename, operation)
            return {'time': time.time(),
                    'filename': filename,
                    'op': operation}
    return _WS


class DirWatchPubSub(object):
    """Pubsub dirwatch events."""

    def __init__(self, root, impl=None, watches=None):
        self.root = root
        self.impl = impl or {}
        self.watches = watches or []

        self.watcher = dirwatch.DirWatcher()
        self.watcher.on_created = self._on_created
        self.watcher.on_deleted = self._on_deleted
        self.watcher.on_modified = self._on_modified

        self.watch_dirs = set()
        for watch in self.watches:
            watch_dirs = self._get_watch_dirs(watch)
            self.watch_dirs.update(watch_dirs)
        for directory in self.watch_dirs:
            _LOGGER.info('Added permanent dir watcher: %s', directory)
            self.watcher.add_dir(directory)

        self.ws = make_handler(self)
        self.handlers = collections.defaultdict(list)

    def register(self, watch, pattern, ws_handler, impl, since):
        """Register handler with pattern."""
        watch_dirs = self._get_watch_dirs(watch)
        for directory in watch_dirs:
            if ((not self.handlers[directory] and
                 directory not in self.watch_dirs)):
                _LOGGER.info('Added dir watcher: %s', directory)
                self.watcher.add_dir(directory)

            self.handlers[directory].append((pattern, ws_handler, impl))
        self._sow(watch, pattern, since, ws_handler, impl)

    def _get_watch_dirs(self, watch):
        pathname = os.path.realpath(os.path.join(self.root, watch.lstrip('/')))
        return [path for path in glob.glob(pathname) if os.path.isdir(path)]

    @utils.exit_on_unhandled
    def _on_created(self, path):
        """On file created callback."""
        _LOGGER.debug('created: %s', path)
        self._handle('c', path)

    @utils.exit_on_unhandled
    def _on_modified(self, path):
        """On file modified callback."""
        _LOGGER.debug('modified: %s', path)
        self._handle('m', path)

    @utils.exit_on_unhandled
    def _on_deleted(self, path):
        """On file deleted callback."""
        _LOGGER.debug('deleted: %s', path)
        self._handle('d', path)

    def _handle(self, operation, path):
        """Get event data and notify interested handlers of the change."""
        directory, filename = os.path.split(path)

        # Ignore (.) files, as they are temporary or "system".
        if filename[0] == '.':
            return

        handlers = [
            (pattern, handler, impl)
            for pattern, handler, impl in self.handlers.get(directory, [])
            if handler.active() and fnmatch.fnmatch(filename, pattern)
        ]
        if not handlers:
            return

        if operation == 'd':
            when = time.time()
            content = None
        else:
            try:
                when = os.stat(path).st_mtime
                with io.open(path) as f:
                    content = f.read()
            except (IOError, OSError) as err:
                if err.errno == errno.ENOENT:
                    # If file was already deleted, it will be handled as 'd'.
                    return
                raise

        self._notify(handlers, path, operation, content, when)

    def _notify(self, handlers, path, operation, content, when):
        """Notify interested handlers of the change."""
        root_len = len(self.root)

        for pattern, handler, impl in handlers:
            try:
                payload = impl.on_event(path[root_len:],
                                        operation,
                                        content)
                if payload is not None:
                    _LOGGER.debug('notify: %s, %s (%s)',
                                  path, operation, pattern)
                    payload['when'] = when
                    handler.write_message(payload)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception('Error handling event')
                handler.send_error_msg(
                    '{cls}: {err}'.format(
                        cls=type(err).__name__,
                        err=str(err)
                    )
                )

    def _db_records(self, db_path, sow_table, watch, pattern, since):
        """Get matching records from db."""
        _LOGGER.info('Using sow db: %s, sow table: %s, watch: %s, pattern: %s',
                     db_path, sow_table, watch, pattern)
        conn = sqlite3.connect(db_path)

        # Before Python 3.7 GLOB pattern must not be parametrized to use index.
        select_stmt = """
            SELECT timestamp, path, data FROM %s
            WHERE directory GLOB ? AND name GLOB '%s' AND timestamp >= ?
            ORDER BY timestamp
        """ % (sow_table, pattern)

        # Return open connection, as conn.execute is cursor iterator, not
        # materialized list.
        return conn, conn.execute(select_stmt, (watch, since,))

    def _sow(self, watch, pattern, since, handler, impl):
        """Publish state of the world."""
        if since is None:
            since = 0

        def _publish(item):
            when, path, content = item
            try:
                payload = impl.on_event(str(path), None, content)
                if payload is not None:
                    payload['when'] = when
                    handler.write_message(payload)
            except Exception as err:  # pylint: disable=W0703
                handler.send_error_msg(str(err))

        db_connections = []
        fs_records = self._get_fs_sow(watch, pattern, since)

        sow = getattr(impl, 'sow', None)
        sow_table = getattr(impl, 'sow_table', 'sow')
        try:
            records = []
            if sow:
                dbs = sorted(glob.glob(os.path.join(self.root, sow, '*')))
                for db in dbs:
                    if os.path.basename(db).startswith('.'):
                        continue

                    conn, db_cursor = self._db_records(
                        db, sow_table, watch, pattern, since
                    )
                    records.append(db_cursor)
                    # FIXME: Figure out pylint use before assign
                    db_connections.append(conn)  # pylint: disable=E0601

            records.append(fs_records)
            # Merge db and fs records, removing duplicates.
            prev_path = None

            for item in heapq.merge(*records):
                _when, path, _content = item
                if path == prev_path:
                    continue
                prev_path = path
                _publish(item)
        finally:
            for conn in db_connections:
                if conn:
                    conn.close()

    def _get_fs_sow(self, watch, pattern, since):
        """Get state of the world from filesystem."""
        root_len = len(self.root)
        fs_glob = os.path.join(self.root, watch.lstrip('/'), pattern)

        files = glob.glob(fs_glob)

        items = []
        for filename in files:
            try:
                stat = os.stat(filename)
                with io.open(filename) as f:
                    content = f.read()
                if stat.st_mtime >= since:
                    path, when = filename[root_len:], stat.st_mtime
                    items.append((when, path, content))
            except (IOError, OSError) as err:
                # Ignore deleted files.
                if err.errno != errno.ENOENT:
                    raise

        return sorted(items)

    def _gc(self):
        """Remove disconnected websocket handlers."""

        for directory in self.handlers.keys():
            handlers = [(pattern, handler, impl)
                        for pattern, handler, impl in self.handlers[directory]
                        if handler.active()]

            _LOGGER.info('Number of active handlers for %s: %s',
                         directory, len(handlers))

            if not handlers:
                _LOGGER.info('No active handlers for %s', directory)
                self.handlers.pop(directory, None)
                if directory not in self.watch_dirs:
                    # Watch is not permanent, remove dir from watcher.
                    self.watcher.remove_dir(directory)
            else:
                self.handlers[directory] = handlers

    @utils.exit_on_unhandled
    def run(self, once=False):
        """Run event loop."""
        last_gc = time.time()
        while True:
            wait_interval = 10
            if once:
                wait_interval = 0

            if self.watcher.wait_for_events(wait_interval):
                self.watcher.process_events()

            if (time.time() - last_gc) >= wait_interval:
                self._gc()
                last_gc = time.time()

            if once:
                break

    @utils.exit_on_unhandled
    def run_detached(self):
        """Run event loop in separate thread."""
        event_thread = threading.Thread(target=self.run)
        event_thread.daemon = True
        event_thread.start()
