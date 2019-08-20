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
import re
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


class AggregateFuture(tornado.concurrent.Future):
    """Aggregation future to get done state if all depending future is done
    """

    def __init__(self, name):
        super(AggregateFuture, self).__init__()
        self._not_ready = set()
        self._ready_for_finish = False
        self._name = name
        self._total = 0

    def ready_for_finish(self):
        """set ready for finish
        if no pending, we directly set result
        """
        self._ready_for_finish = True
        if not self._not_ready:
            self.set_result(self._total)

    def depend(self, future):
        """add more dependency for ready
        """
        self._total += 1
        self._not_ready.add(id(future))
        future.add_done_callback(self._done_callback)

    def _done_callback(self, future):
        """future complete"""
        self._not_ready.remove(id(future))
        if self._ready_for_finish and (not self._not_ready):
            _LOGGER.info('Future %s is to finish, %d aggregated.',
                         self._name, self._total)
            self.set_result(self._total)


def make_handler(pubsub):
    """Make websocket handler factory."""
    # pylint: disable=too-many-statements

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

        def open(self, *args, **kwargs):
            """Called when connection is opened.

            Override if you want to do something else besides log the action.
            """
            _LOGGER.info('[%s] Connection opened, remote ip: %s',
                         self._request_id, self.request.remote_ip)

        def send_msg(self, msg):
            """Send message."""
            _LOGGER.info('[%s] Sending message: %r', self._request_id, msg)
            try:
                future = self.write_message(msg)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('[%s] Error sending message: %r',
                                  self._request_id, msg)
            return future

        def close_with_log(self):
            """close current handler's socket with logging id
            """
            _LOGGER.info('[%s] Closing connection.', self._request_id)
            self.close()

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

            future = self.send_msg(error_msg)
            if close_conn:
                future.add_done_callback(lambda _f: self.close_with_log())

            return future

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

        def on_message(self, message):
            """Manage event subscriptions."""
            if not pubsub:
                _LOGGER.fatal('pubsub is not configured, ignore.')
                self.send_error_msg('Fatal: unexpected error', close_conn=True)

            _LOGGER.info('[%s] Received message: %s',
                         self._request_id, message)

            sub_id = None
            close_conn = True
            try:
                sub_msg = json.loads(message)

                sub_id = sub_msg.get('sub-id')
                close_conn = sub_id is None

                if sub_msg.get('unsubscribe') is True:
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

                topic = sub_msg.get('topic')
                impl = pubsub.impl.get(topic)
                if not impl:
                    self.send_error_msg(
                        'Invalid topic: %s' % topic,
                        sub_id=sub_id, close_conn=close_conn
                    )
                    return

                subscription = impl.subscribe(sub_msg)
                since = sub_msg.get('since', 0)
                snapshot = sub_msg.get('snapshot', False)

                if sub_id and not snapshot:
                    _LOGGER.info('[%s] Adding subscription %s',
                                 self._request_id, sub_id)
                    self._subscriptions.add(sub_id)

                sub_future = AggregateFuture('subscribe')
                # if snapshot mode, we close handler socket after sow is done
                if snapshot and close_conn:
                    sub_future.add_done_callback(
                        lambda _f: self.close_with_log()
                    )

                for watch, pattern in subscription:
                    future = pubsub.register(
                        watch, pattern, self, impl, since, sub_id
                    )
                    sub_future.depend(future)

                sub_future.ready_for_finish()

            except Exception as err:  # pylint: disable=W0703
                self.send_error_msg(str(err),
                                    sub_id=sub_id, close_conn=close_conn)

        def data_received(self, chunk):
            """Passthrough of abstract method data_received.
            """

        def on_event(self, filename, operation, _content):
            """Default event handler."""
            _LOGGER.debug('%s %s', filename, operation)
            return {'time': time.time(),
                    'filename': filename,
                    'op': operation}
    return _WS


class DirWatchPubSub:
    """Pubsub dirwatch events."""

    def __init__(self, root, impl=None, watches=None):
        self.root = os.path.realpath(root)
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
        """Register handler with pattern.
        return `tornado.concurrent.Future`
        future will be done when sow completes
        """
        watch_dirs = self._get_watch_dirs(watch)
        for directory in watch_dirs:
            if ((not self.handlers[directory] and
                 directory not in self.watch_dirs)):
                _LOGGER.info('Added dir watcher: %s', directory)
                self.watcher.add_dir(directory)

            # Store pattern as precompiled regex.
            pattern_re = re.compile(
                fnmatch.translate(pattern)
            )
            self.handlers[directory].append(
                (pattern_re, ws_handler, impl, sub_id)
            )
        return self._sow(
            watch, pattern, since, ws_handler, impl,
            sub_id=sub_id
        )

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
            (handler, impl, sub_id)
            for pattern_re, handler, impl, sub_id in directory_handlers
            if (handler.active(sub_id=sub_id) and
                pattern_re.match(filename))
        ]
        if not handlers:
            return

        if operation == 'd':
            when = time.time()
            content = None
        else:
            if '/trace/' in path or '/server-trace/' in path:
                # Specialized handling of trace files (no need to stat/read).
                # If file was already deleted (trace cleanup), don't ignore it.
                _, timestamp, _ = filename.split(',', 2)
                when, content = float(timestamp), ''
            else:
                try:
                    when = os.stat(path).st_mtime
                    with io.open(path) as f:
                        content = f.read()
                except (IOError, OSError) as err:
                    if err.errno == errno.ENOENT:
                        # If file was already deleted, ignore.
                        # It will be handled as 'd'.
                        return
                    raise

        self._notify(handlers, path, operation, content, when)

    def _notify(self, handlers, path, operation, content, when):
        """Notify interested handlers of the change."""
        root_len = len(self.root)

        for handler, impl, sub_id in handlers:
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

    # pylint: disable=too-many-branches
    def _sow(self, watch, pattern, since, handler, impl, sub_id=None):
        """Publish state of the world."""
        if since is None:
            since = 0

        def _publish(item):
            when, path, content = item
            future = None
            try:
                payload = impl.on_event(str(path), None, content)
                if payload is not None:
                    payload['when'] = when
                    if sub_id is not None:
                        payload['sub-id'] = sub_id
                    future = handler.send_msg(payload)
            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Error handling sow event: %s, %s, %s, %s',
                                  path, content, when, sub_id)
                future = handler.send_error_msg(str(err), sub_id=sub_id)

            return future

        sow_future = AggregateFuture('sow[{}]'.format(pattern))
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
                future = _publish(item)
                if future is not None:
                    sow_future.depend(future)

            # sow future will be done after all send_msg() are done
            sow_future.ready_for_finish()
        finally:
            for conn in db_connections:
                if conn:
                    conn.close()

        return sow_future

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

            _LOGGER.debug('Number of active handlers for %s: %s',
                          directory, len(handlers))

            if not handlers:
                _LOGGER.debug('No active handlers for %s', directory)
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
