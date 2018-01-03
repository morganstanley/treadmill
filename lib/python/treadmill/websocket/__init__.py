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
import uuid

import tornado.websocket

import six
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
            self._request_id = str(uuid.uuid4())
            self._subscriptions = set()

        def active(self, sub_id=None):
            """Return true if connection (and optional subscription) is active,
            false otherwise.

            If connection is not active, so are all of its subscriptions.
            """
            if not self.ws_connection:
                return False
            return sub_id is None or sub_id in self._subscriptions

        def open(self):
            """Called when connection is opened.

            Override if you want to do something else besides log the action.
            """
            _LOGGER.info('[%s] Connection opened, remote ip: %s',
                         self._request_id, self.request.remote_ip)

        def send_msg(self, msg):
            """Send message."""
            _LOGGER.info('[%s] Sending message: %r', self._request_id, msg)
            try:
                self.write_message(msg)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('[%s] Error sending message: %r',
                                  self._request_id, msg)

        def send_error_msg(self, error_str, sub_id=None, close_conn=True):
            """Convenience method for logging and returning errors.

            If sub_id is provided, it will be included in the error message and
            subscription will be removed.

            Note: this method will close the connection after sending back the
            error, unless close_conn=False.
            """
            error_msg = {'_error': error_str,
                         'when': time.time()}
            if sub_id is not None:
                error_msg['sub-id'] = sub_id
                _LOGGER.info('[%s] Removing subscription %s',
                             self._request_id, sub_id)
                try:
                    self._subscriptions.remove(sub_id)
                except KeyError:
                    pass

            self.send_msg(error_msg)

            if close_conn:
                _LOGGER.info('[%s] Closing connection.', self._request_id)
                self.close()

        def on_close(self):
            """Called when connection is closed.

            Override if you want to do something else besides log the action.
            """
            _LOGGER.info('[%s] Connection closed.', self._request_id)

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

            _LOGGER.info('[%s] Received message: %s',
                         self._request_id, jmessage)

            sub_id = None
            close_conn = True
            try:
                message = json.loads(jmessage)

                sub_id = message.get('sub-id')
                close_conn = sub_id is None

                if message.get('unsubscribe') is True:
                    _LOGGER.info('[%s] Unsubscribing %s',
                                 self._request_id, sub_id)
                    try:
                        self._subscriptions.remove(sub_id)
                    except KeyError:
                        self.send_error_msg(
                            'Invalid subscription: %s' % sub_id,
                            close_conn=False
                        )
                    return

                if sub_id and sub_id in self._subscriptions:
                    self.send_error_msg(
                        'Subscription already exists: %s' % sub_id,
                        close_conn=False
                    )
                    return

                topic = message.get('topic')
                impl = pubsub.impl.get(topic)
                if not impl:
                    self.send_error_msg(
                        'Invalid topic: %s' % topic,
                        sub_id=sub_id, close_conn=close_conn
                    )
                    return

                subscription = impl.subscribe(message)
                since = message.get('since', 0)
                snapshot = message.get('snapshot', False)

                if sub_id and not snapshot:
                    _LOGGER.info('[%s] Adding subscription %s',
                                 self._request_id, sub_id)
                    self._subscriptions.add(sub_id)

                for watch, pattern in subscription:
                    pubsub.register(watch, pattern, self, impl, since, sub_id)
                if snapshot and close_conn:
                    _LOGGER.info('[%s] Closing connection.', self._request_id)
                    self.close()

            except Exception as err:  # pylint: disable=W0703
                self.send_error_msg(str(err),
                                    sub_id=sub_id, close_conn=close_conn)

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

    def register(self, watch, pattern, ws_handler, impl, since, sub_id=None):
        """Register handler with pattern."""
        watch_dirs = self._get_watch_dirs(watch)
        for directory in watch_dirs:
            if ((not self.handlers[directory] and
                 directory not in self.watch_dirs)):
                _LOGGER.info('Added dir watcher: %s', directory)
                self.watcher.add_dir(directory)

            self.handlers[directory].append(
                (pattern, ws_handler, impl, sub_id)
            )
        self._sow(watch, pattern, since, ws_handler, impl, sub_id=sub_id)

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

        directory_handlers = self.handlers.get(directory, [])
        handlers = [
            (pattern, handler, impl, sub_id)
            for pattern, handler, impl, sub_id in directory_handlers
            if (handler.active(sub_id=sub_id) and
                fnmatch.fnmatch(filename, pattern))
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

        for _pattern, handler, impl, sub_id in handlers:
            try:
                payload = impl.on_event(path[root_len:],
                                        operation,
                                        content)
                if payload is not None:
                    payload['when'] = when
                    if sub_id is not None:
                        payload['sub-id'] = sub_id
                    handler.send_msg(payload)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception('Error handling event: %s, %s, %s, %s, %s',
                                  path, operation, content, when, sub_id)
                handler.send_error_msg(
                    '{cls}: {err}'.format(
                        cls=type(err).__name__,
                        err=str(err)
                    ),
                    sub_id=sub_id,
                    close_conn=sub_id is None
                )

    def _db_records(self, db_path, sow_table, watch, pattern, since):
        """Get matching records from db."""
        # if file does not exist, do not try to open it. Opening connection
        # will create the file, there is no way to prevent this from
        # happening until py3.
        #
        if not os.path.exists(db_path):
            _LOGGER.info('Ignore deleted db: %s', db_path)
            return (None, None)

        # There is rare condition that the db file is deleted HERE. In this
        # case connection will be open, but the tables will not be there.
        conn = sqlite3.connect(db_path)

        # Before Python 3.7 GLOB pattern must not be parametrized to use index.
        select_stmt = """
            SELECT timestamp, path, data FROM %s
            WHERE directory GLOB ? AND name GLOB '%s' AND timestamp >= ?
            ORDER BY timestamp
        """ % (sow_table, pattern)

        # Return open connection, as conn.execute is cursor iterator, not
        # materialized list.
        try:
            return conn, conn.execute(select_stmt, (watch, since,))
        except sqlite3.OperationalError as db_err:
            # Not sure if the file needs to be deleted at this point. As
            # sow_table is a parameter, passing non-existing table can cause
            # legit file to be deleted.
            _LOGGER.info('Unable to execute: select from %s:%s ..., %s',
                         db_path, sow_table, str(db_err))
            conn.close()
            return (None, None)

    def _sow(self, watch, pattern, since, handler, impl, sub_id=None):
        """Publish state of the world."""
        if since is None:
            since = 0

        def _publish(item):
            when, path, content = item
            try:
                payload = impl.on_event(str(path), None, content)
                if payload is not None:
                    payload['when'] = when
                    if sub_id is not None:
                        payload['sub-id'] = sub_id
                    handler.send_msg(payload)
            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Error handling sow event: %s, %s, %s, %s',
                                  path, content, when, sub_id)
                handler.send_error_msg(str(err), sub_id=sub_id)

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
                    if db_cursor:
                        records.append(db_cursor)

                    # FIXME: Figure out pylint use before assign
                    #
                    # pylint: disable=E0601
                    if conn:
                        db_connections.append(conn)

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
        for directory in list(six.viewkeys(self.handlers)):
            handlers = [
                (pattern, handler, impl, sub_id)
                for pattern, handler, impl, sub_id in self.handlers[directory]
                if handler.active(sub_id=sub_id)
            ]

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
