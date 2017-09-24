"""Unit test for websocket.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest

import mock
from tornado import gen
from tornado import web
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase
from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from treadmill import websocket
from treadmill import fs


class DummyHandler(object):
    """Dummy handler to test pubsub functionality."""

    def __init__(self, *_args, **_kwargs):
        # Explicitely do not call __init__ of the base.
        #
        # pylint: disable=W0231
        self.events = []

    def subscribe(self, _message):
        """noop."""
        return []

    def on_event(self, filename, operation, content):
        """Append event for further validation."""
        self.events.append((filename, operation, content))


class PubSubTest(unittest.TestCase):
    """Test Websocket dirwatch pubsub."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_pubsub(self):
        """Tests subscription."""
        pubsub = websocket.DirWatchPubSub(self.root)
        handler1 = DummyHandler()
        handler2 = DummyHandler()

        io.open(os.path.join(self.root, 'xxx'), 'w').close()
        io.open(os.path.join(self.root, 'aaa'), 'w').close()

        ws1 = mock.Mock()
        ws2 = mock.Mock()

        ws1.active.return_value = True
        ws2.active.return_value = True

        pubsub.register('/', '*', ws1, handler1, True)
        pubsub.register('/', 'a*', ws2, handler2, True)

        self.assertEqual(2, len(pubsub.handlers[self.root]))

        self.assertIn(('/aaa', None, ''), handler1.events)
        self.assertIn(('/xxx', None, ''), handler1.events)
        self.assertEqual(
            [('/aaa', None, '')],
            handler2.events
        )

        with io.open(os.path.join(self.root, 'abc'), 'w') as f:
            f.write('x')
        with io.open(os.path.join(self.root, '.abc'), 'w') as f:
            f.write('x')

        pubsub.run(once=True)

        self.assertIn(('/abc', 'c', 'x'), handler1.events)
        self.assertIn(('/abc', 'm', 'x'), handler1.events)
        self.assertIn(('/abc', 'c', 'x'), handler2.events)
        self.assertIn(('/abc', 'm', 'x'), handler2.events)
        self.assertNotIn(('/.abc', 'c', 'x'), handler1.events)
        self.assertNotIn(('/.abc', 'c', 'x'), handler2.events)

        # Simulate connection close.
        ws1.active.return_value = False

        pubsub.run(once=True)
        self.assertEqual(1, len(pubsub.handlers[self.root]))

    def test_sow_since(self):
        """Tests sow since handling."""
        # Access to protected member: _sow
        #
        # pylint: disable=W0212
        pubsub = websocket.DirWatchPubSub(self.root)
        handler = mock.Mock()
        impl = mock.Mock()
        impl.sow = None
        impl.on_event.side_effect = [
            {'echo': 1},
            {'echo': 2},
        ]
        io.open(os.path.join(self.root, 'xxx'), 'w').close()
        modified = os.stat(os.path.join(self.root, 'xxx')).st_mtime

        pubsub._sow('/', '*', 0, handler, impl)

        handler.write_message.assert_called_with(
            {'echo': 1, 'when': modified},
        )
        handler.write_message.reset_mock()

        pubsub._sow('/', '*', time.time() + 1, handler, impl)
        self.assertFalse(handler.write_message.called)
        handler.write_message.reset_mock()

        pubsub._sow('/', '*', time.time() - 1, handler, impl)
        handler.write_message.assert_called_with(
            {'echo': 2, 'when': modified},
        )
        handler.write_message.reset_mock()

    def test_sow_fs_and_db(self):
        """Tests sow from filesystem and database."""
        # Access to protected member: _sow
        #
        # pylint: disable=W0212
        pubsub = websocket.DirWatchPubSub(self.root)

        handler = mock.Mock()

        impl = mock.Mock()
        sow_dir = os.path.join(self.root, '.sow', 'trace')
        fs.mkdir_safe(sow_dir)

        with tempfile.NamedTemporaryFile(dir=sow_dir,
                                         delete=False,
                                         prefix='trace.db-') as temp:
            pass
        impl.sow = sow_dir
        impl.sow_table = 'trace'

        conn = sqlite3.connect(temp.name)
        conn.execute(
            """
            CREATE TABLE trace (
                path text, timestamp integer, data text,
                directory text, name text
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO trace (
                path, timestamp, directory, name
            ) VALUES(?, ?, ?, ?)
            """,
            [('/aaa', 3, '/', 'aaa'),
             ('/bbb', 2, '/', 'bbb'),
             ('/ccc', 1, '/', 'ccc')]
        )
        conn.commit()
        conn.close()

        impl.on_event.side_effect = [
            {'echo': 1},
            {'echo': 2},
            {'echo': 3},
            {'echo': 4},
        ]

        io.open(os.path.join(self.root, 'xxx'), 'w').close()
        modified = os.stat(os.path.join(self.root, 'xxx')).st_mtime

        pubsub._sow('/', '*', 0, handler, impl)

        impl.on_event.assert_has_calls(
            [
                mock.call('/ccc', None, None),
                mock.call('/bbb', None, None),
                mock.call('/aaa', None, None),
                mock.call('/xxx', None, ''),
            ]
        )
        handler.write_message.assert_has_calls(
            [
                mock.call({'when': 1, 'echo': 1}),
                mock.call({'when': 2, 'echo': 2}),
                mock.call({'when': 3, 'echo': 3}),
                mock.call({'when': modified, 'echo': 4}),
            ]
        )

    @mock.patch('glob.glob')
    @mock.patch('os.path.isdir')
    @mock.patch('treadmill.dirwatch.DirWatcher')
    @mock.patch('treadmill.websocket.DirWatchPubSub._sow', mock.Mock())
    def test_permanent_watches(self, watcher_cls_mock, isdir_mock, glob_mock):
        """Tests permanent watches."""
        # Access to protected member: _gc
        #
        # pylint: disable=W0212

        # Add permanent watches
        watcher_mock = mock.Mock()
        watcher_cls_mock.return_value = watcher_mock
        glob_mock.return_value = ['/root/test/foo', '/root/test/bar']
        isdir_mock.side_effect = [True, False]

        pubsub = websocket.DirWatchPubSub('/root', watches=['/test/*'])

        glob_mock.assert_called_once_with('/root/test/*')
        watcher_mock.add_dir.assert_called_once_with('/root/test/foo')

        # Register on permanent watch should not add dir again
        ws_handler_mock = mock.Mock()
        impl_mock = mock.Mock()
        isdir_mock.side_effect = [True, False]

        pubsub.register('/test/*', '*', ws_handler_mock, impl_mock, None)

        self.assertEqual(watcher_mock.add_dir.call_count, 1)  # No new calls.
        self.assertIn('/root/test/foo', pubsub.handlers)

        # Do not GC permanent watches
        ws_handler_mock.active.return_value = False

        pubsub._gc()

        self.assertEqual(watcher_mock.remove_dir.call_count, 0)


class WebSocketTest(AsyncHTTPTestCase):
    """Base class for all unit test classes below, basically wraps up the
    websocket_connect and the close"""

    def setUp(self):
        """Setup test"""
        self.root = tempfile.mkdtemp()
        self.pubsub = websocket.DirWatchPubSub(self.root)
        AsyncHTTPTestCase.setUp(self)

    def tearDown(self):
        AsyncHTTPTestCase.tearDown(self)
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @gen.coroutine
    def ws_connect(self, path):
        """Wrapper method to help setup a new websocket connection"""
        ws = yield websocket_connect(
            'ws://127.0.0.1:%d%s' % (self.get_http_port(), path))
        raise gen.Return(ws)

    @gen.coroutine
    def close(self, webs):
        """Close a websocket connection and wait for the server side.
        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        webs.close()
        yield self.close_future

    def get_app(self):
        """Set up all the servers and their paths"""
        self.close_future = Future()

        return web.Application([
            (r'/', self.pubsub.ws),
        ])

    @gen_test
    def test_echo(self):
        """Test return of the same value sent, i.e. echo server"""
        io.open(os.path.join(self.root, 'xxx'), 'w').close()

        echo_impl = mock.Mock()
        echo_impl.sow = None
        echo_impl.subscribe.return_value = [('/', '*')]
        echo_impl.on_event.return_value = {'echo': 1}
        self.pubsub.impl['echo'] = echo_impl

        ws = yield self.ws_connect('/')
        echo_msg = '{"topic": "echo"}'
        ws.write_message(echo_msg)
        self.pubsub.run(once=True)
        response = yield ws.read_message()
        self.assertEqual(1, json.loads(response)['echo'])
        self.assertIn('when', json.loads(response))

    @gen_test
    def test_snapshot(self):
        """Test return of the same value sent, i.e. echo server"""
        io.open(os.path.join(self.root, 'xxx'), 'w').close()

        echo_impl = mock.Mock()
        echo_impl.sow = None
        echo_impl.subscribe.return_value = [('/', '*')]
        echo_impl.on_event.return_value = {'echo': 1}
        self.pubsub.impl['echo'] = echo_impl

        ws = yield self.ws_connect('/')
        echo_msg = '{"topic": "echo", "snapshot": 1}'
        ws.write_message(echo_msg)
        self.pubsub.run(once=True)
        response = yield ws.read_message()

        self.assertEqual(1, json.loads(response)['echo'])
        self.assertIn('when', json.loads(response))

        response = yield ws.read_message()
        self.assertIsNone(response)


if __name__ == '__main__':
    unittest.main()
