"""Unit test for websocket.
"""

import json
import unittest
import tempfile
import os
import shutil
import time
import sqlite3

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock
from tornado import gen
from tornado import web
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase
from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from treadmill import websocket


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

        open(os.path.join(self.root, 'xxx'), 'w+').close()
        open(os.path.join(self.root, 'aaa'), 'w+').close()

        ws1 = mock.Mock()
        ws2 = mock.Mock()

        ws1.active.return_value = True
        ws2.active.return_value = True

        pubsub.register('/', '*', ws1, handler1, True)
        pubsub.register('/', 'a*', ws2, handler2, True)

        self.assertEquals(2, len(pubsub.handlers[self.root]))

        self.assertIn(('/aaa', None, ''), handler1.events)
        self.assertIn(('/xxx', None, ''), handler1.events)
        self.assertEquals(
            [('/aaa', None, '')],
            handler2.events
        )

        with open(os.path.join(self.root, 'abc'), 'w+') as f:
            f.write('x')
        with open(os.path.join(self.root, '.abc'), 'w+') as f:
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
        self.assertEquals(1, len(pubsub.handlers[self.root]))

        pubsub.register('/new_dir', 'bbb', ws2, handler2, True)
        self.assertTrue(os.path.exists(os.path.join(self.root, 'new_dir')))

    def test_sow_since(self):
        """Tests sow since handling."""
        # Access to protected member: _sow
        #
        # pylint: disable=W0212
        pubsub = websocket.DirWatchPubSub(self.root)
        handler = mock.Mock()
        impl = mock.Mock()
        impl.sow_db = None
        impl.on_event.return_value = {'echo': 1}
        open(os.path.join(self.root, 'xxx'), 'w+').close()
        modified = int(os.stat(os.path.join(self.root, 'xxx')).st_mtime)

        pubsub._sow(self.root, '*', 0, handler, impl)

        handler.write_message.assert_called_with(
            json.dumps({'echo': 1, 'when': modified}),
        )
        handler.write_message.reset_mock()

        pubsub._sow(self.root, '*', time.time() + 1, handler, impl)
        self.assertFalse(handler.write_message.called)
        handler.write_message.reset_mock()

        pubsub._sow(self.root, '*', time.time() - 1, handler, impl)
        handler.write_message.assert_called_with(
            json.dumps({'echo': 1, 'when': modified}),
        )
        handler.write_message.reset_mock()

    @mock.patch('sqlite3.connect', mock.Mock())
    def test_sow_fs_and_db(self):
        """Tests sow from filesystem and database."""
        # Access to protected member: _sow
        #
        # pylint: disable=W0212
        pubsub = websocket.DirWatchPubSub(self.root)

        handler = mock.Mock()

        impl = mock.Mock()
        impl.sow_db = '.tasks-sow.db'
        impl.on_event.return_value = {'echo': 1}

        open(os.path.join(self.root, 'xxx'), 'w+').close()
        modified = int(os.stat(os.path.join(self.root, 'xxx')).st_mtime)

        conn_mock = mock.Mock()
        cur_mock = mock.Mock()
        sqlite3.connect.return_value = conn_mock
        conn_mock.cursor.return_value = cur_mock
        cur_mock.fetchall.return_value = [
            ('/aaa', 1, ''),
            ('/bbb', 2, ''),
            ('/ccc', 3, ''),
        ]

        pubsub._sow(self.root, '*', 0, handler, impl)

        self.assertEquals(
            impl.on_event.call_args_list,
            [
                mock.call('/aaa', None, ''),
                mock.call('/bbb', None, ''),
                mock.call('/ccc', None, ''),
                mock.call('/xxx', None, '')
            ]
        )
        self.assertEquals(
            handler.write_message.call_args_list,
            [
                mock.call('{"when": 1, "echo": 1}'),
                mock.call('{"when": 2, "echo": 1}'),
                mock.call('{"when": 3, "echo": 1}'),
                mock.call('{"when": %s, "echo": 1}' % modified)
            ]
        )


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
        open(os.path.join(self.root, 'xxx'), 'w+').close()

        echo_impl = mock.Mock()
        echo_impl.sow_db = None
        echo_impl.subscribe.return_value = [('/', '*')]
        echo_impl.on_event.return_value = {'echo': 1}
        self.pubsub.impl['echo'] = echo_impl

        ws = yield self.ws_connect('/')
        echo_msg = '{"topic": "echo"}'
        ws.write_message(echo_msg)
        self.pubsub.run(once=True)
        response = yield ws.read_message()
        self.assertEquals(1, json.loads(response)['echo'])
        self.assertIn('when', json.loads(response))

    @gen_test
    def test_snapshot(self):
        """Test return of the same value sent, i.e. echo server"""
        open(os.path.join(self.root, 'xxx'), 'w+').close()

        echo_impl = mock.Mock()
        echo_impl.sow_db = None
        echo_impl.subscribe.return_value = [('/', '*')]
        echo_impl.on_event.return_value = {'echo': 1}
        self.pubsub.impl['echo'] = echo_impl

        ws = yield self.ws_connect('/')
        echo_msg = '{"topic": "echo", "snapshot": 1}'
        ws.write_message(echo_msg)
        self.pubsub.run(once=True)
        response = yield ws.read_message()

        self.assertEquals(1, json.loads(response)['echo'])
        self.assertIn('when', json.loads(response))

        response = yield ws.read_message()
        self.assertIsNone(response)


if __name__ == '__main__':
    unittest.main()
