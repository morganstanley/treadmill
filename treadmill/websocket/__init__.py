"""Websocket API."""


import collections
import datetime
import errno
import glob
import fnmatch
import logging
import threading
import urllib.parse
import os
import time

import json
import tornado.websocket

from treadmill import idirwatch
from treadmill import exc
from treadmill import fs


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
                         'when': datetime.datetime.utcnow().isoformat()}

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
            parsed_origin = urllib.parse.urlparse(origin)
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
                for directory, pattern in impl.subscribe(message):
                    pubsub.register(directory, pattern, self, impl, since)
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

    def __init__(self, root):
        self.handlers = collections.defaultdict(list)
        self.impl = dict()
        self.root = root

        self.watcher = idirwatch.DirWatcher()
        self.watcher.on_created = self._on_created
        self.watcher.on_deleted = self._on_deleted
        self.watcher.on_modified = self._on_modified

        self.ws = make_handler(self)

    def register(self, directory, pattern, ws_handler, impl, since):
        """Register handler with pattern."""
        norm_path = os.path.realpath(os.path.join(self.root,
                                                  directory.lstrip('/')))
        if not self.handlers[norm_path]:
            _LOGGER.info('Added dir watcher: %s', directory)
            fs.mkdir_safe(norm_path)
            self.watcher.add_dir(norm_path)

        self.handlers[norm_path].append((pattern, ws_handler, impl))
        self._sow(norm_path, pattern, since, ws_handler, impl)

    @exc.exit_on_unhandled
    def _on_created(self, filename):
        """On file created callback."""
        _LOGGER.debug('created: %s', filename)
        self._handle('c', filename)

    @exc.exit_on_unhandled
    def _on_modified(self, filename):
        """On file modified callback."""
        _LOGGER.debug('modified: %s', filename)
        self._handle('m', filename)

    @exc.exit_on_unhandled
    def _on_deleted(self, filename):
        """On file deleted callback."""
        _LOGGER.debug('deleted: %s', filename)
        self._notify(filename, 'd', None)

    def _handle(self, operation, filename):
        """Read file event, notify all handlers."""
        _LOGGER.debug('modified: %s', filename)

        try:
            with open(filename) as f:
                content = f.read()
        except IOError as err:
            if err.errno != errno.ENOENT:
                raise

            operation = 'd'
            content = None

        self._notify(filename, operation, content)

    def _notify(self, path, operation, content):
        """Notify all handlers of the change."""
        root_len = len(self.root)
        directory = os.path.dirname(path)
        filename = os.path.basename(path)

        for pattern, handler, impl in self.handlers[directory]:
            if not handler.active():
                continue

            if fnmatch.fnmatch(filename, pattern):
                try:
                    payload = impl.on_event(path[root_len:],
                                            operation,
                                            content)
                    if payload is not None:
                        handler.write_message(json.dumps(payload))
                except Exception as err:  # pylint: disable=W0703
                    _LOGGER.exception('ahh')
                    handler.send_error_msg(str(err))

    def _sow(self, directory, pattern, since, handler, impl):
        """Publish state of the world."""
        root_len = len(self.root)

        files = glob.glob(os.path.join(directory, pattern))
        files.sort(key=os.path.getmtime)

        for filename in files:
            content = None
            try:
                stat = os.stat(filename)
                if stat.st_mtime < since:
                    continue
                with open(filename) as f:
                    content = f.read()
            except IOError as io_err:
                # Ignore deleted files.
                if io_err.errno != errno.ENOENT:
                    raise
            except OSError as os_err:
                # if we get
                if os_err.errno != errno.ENOENT:
                    raise
            try:
                payload = impl.on_event(filename[root_len:], None, content)
                if payload is not None:
                    handler.write_message(json.dumps(payload))
            except Exception as err:  # pylint: disable=W0703
                handler.send_error_msg(str(err))

    def _gc(self):
        """Remove disconnected websocket handlers."""
        _LOGGER.info('Running gc.')
        for directory in self.handlers.keys():
            handlers = [(pattern, handler, impl)
                        for pattern, handler, impl in self.handlers[directory]
                        if handler.active()]

            if not handlers:
                _LOGGER.info('No active handlers for %s', directory)
                self.watcher.remove_dir(directory)

            _LOGGER.info('Handlers %s, count %s', directory, len(handlers))
            self.handlers[directory] = handlers

    @exc.exit_on_unhandled
    def run(self, once=False):
        """Run event loop."""
        while True:
            wait_interval = 10
            if once:
                wait_interval = 0
            if self.watcher.wait_for_events(wait_interval):
                self.watcher.process_events()
            else:
                self._gc()

            if once:
                break

    @exc.exit_on_unhandled
    def run_detached(self):
        """Run event loop in separate thread."""
        event_thread = threading.Thread(target=self.run)
        event_thread.daemon = True
        event_thread.start()
