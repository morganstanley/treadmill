"""Unit test for the state websocket handler, i.e. state_wshandler.
"""

import json
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock
from tornado import gen
from tornado import web
from tornado.concurrent import Future
from tornado.testing import AsyncHTTPTestCase
from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from treadmill import context
from treadmill import state_wshandler

ALL_NODES = [
    'foo.1#0',
    'foo.1#1',
    'bar.1#0',
    'bar.1#1',
    ]


class WebSocketBaseTestCase(AsyncHTTPTestCase):
    """Base class for all unit test classes below, basically wraps up the
    websocket_connect and the close"""

    def setUp(self):
        """Setup test"""
        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'

        zkclient_mock = mock.Mock()
        zkclient_mock.get_children = mock.MagicMock(return_value=ALL_NODES)
        context.ZkContext.conn = zkclient_mock

        AsyncHTTPTestCase.setUp(self)

    @gen.coroutine
    def ws_connect(self, path):
        """Wrapper method to help setup a new websocket connection"""
        websocket = yield websocket_connect(
            'ws://127.0.0.1:%d%s' % (self.get_http_port(), path))
        raise gen.Return(websocket)

    @gen.coroutine
    def close(self, websocket):
        """Close a websocket connection and wait for the server side.
        If we don't wait here, there are sometimes leak warnings in the
        tests.
        """
        websocket.close()
        yield self.close_future

    def get_app(self):
        """Set up all the servers and their paths"""
        # pylint: disable=W0201
        self.close_future = Future()
        return web.Application([
            ('/state', state_wshandler.StateWebSocketHandler),
            ])


class WebSocketServerTests(WebSocketBaseTestCase):
    """Test cases for Echo server"""

    @gen_test
    def test_all_running(self):
        """This test verifies we can connect, send and receive all
        state.running"""
        websocket = yield self.ws_connect('/state')
        req = {'cell': 'test', 'state': 'running', 'pattern': '*'}
        websocket.write_message(json.dumps(req))
        response_str = yield websocket.read_message()
        response = json.loads(response_str)
        self.assertEqual(4, len(response['running']),
                         "Failed verification that all 4 apps were returned")

    @gen_test
    def test_running(self):
        """This test verifies we can connect, send and receive state.running"""
        websocket = yield self.ws_connect('/state')
        req = {'cell': 'test', 'state': 'running', 'pattern': '*'}
        websocket.write_message(json.dumps(req))
        response_str = yield websocket.read_message()
        response = json.loads(response_str)
        self.assertEqual('test/bar.1#0', response['running'][0],
                         'Failed verification of the first app in'
                         ' state.running')

    @gen_test
    def test_pattern(self):
        """This test verifies that the pattern reduces our search"""
        websocket = yield self.ws_connect('/state')
        req = {'cell': 'test', 'state': 'running', 'pattern': 'foo.*', }
        websocket.write_message(json.dumps(req))
        response_str = yield websocket.read_message()
        response = json.loads(response_str)
        self.assertEqual('test/foo.1#0', response['running'][0],
                         'Failed verification of pattern searching in'
                         ' state.running')


if __name__ == '__main__':
    unittest.main()
