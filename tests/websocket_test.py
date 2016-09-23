"""Unit test for websocket.
"""

import json
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock
from tornado import gen
from tornado import web
from tornado.concurrent import Future
from tornado.httpclient import HTTPError, HTTPRequest
from tornado.testing import AsyncHTTPTestCase
from tornado.testing import gen_test
from tornado.websocket import websocket_connect

from treadmill import context
from treadmill import websocket


class EchoHandlerTest(websocket.WebSocketHandlerBase):
    """Test WebSocketHandlerBase with a simple Echo server"""
    def on_message(self, message):
        """Simple echo/return same message"""
        self.write_message(message)


class ErrorHandlerTest(websocket.WebSocketHandlerBase):
    """Test WebSocketHandlerBase with an error response"""
    def on_message(self, message):
        """Simple echo/return same message"""
        self.send_error_msg("Bad request")


class MisConfiguredHandlerTest(websocket.WebSocketHandlerBase):
    """Test WebSocketHandlerBase with an error response"""


class WebSocketBaseTestCase(AsyncHTTPTestCase):
    """Base class for all unit test classes below, basically wraps up the
    websocket_connect and the close"""

    def setUp(self):
        """Setup test"""
        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'

        zkclient_mock = mock.Mock()
        # zkclient_mock.get_children = mock.MagicMock(return_value=ALL_NODES)
        context.ZkContext.conn = zkclient_mock

        AsyncHTTPTestCase.setUp(self)

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
        # pylint: disable=W0201
        self.close_future = Future()
        return web.Application([
            ('/echo', EchoHandlerTest),
            ('/error', ErrorHandlerTest),
            ('/misconfigured', MisConfiguredHandlerTest),
            ])


class WebSocketServerTests(WebSocketBaseTestCase):
    """Test cases for Echo server"""
    @gen_test
    def test_websocket_http_fail(self):
        """Test failure to get the correct path"""
        with self.assertRaises(HTTPError) as cm:
            yield self.ws_connect('/notfound')
            self.assertEqual(cm.exception.code, 404)

    @gen_test
    def test_echo(self):
        """Test return of the same value sent, i.e. echo server"""
        ws = yield self.ws_connect('/echo')
        test_str = 'test error'
        ws.write_message(test_str)
        response = yield ws.read_message()
        self.assertEqual(test_str, response,
                         "Server did not send {0}, instead sent: {1}"
                         .format(test_str, response))

    @gen_test
    def test_good_check_origin(self):
        """Test good check_origin"""
        port = self.get_http_port()
        url = 'ws://127.0.0.1:%d/echo' % port
        headers = {'Origin': 'http://foo.xx.com'}
        ws = yield websocket_connect(HTTPRequest(url, headers=headers),
                                     io_loop=self.io_loop)
        test_str = 'test error'
        ws.write_message(test_str)
        response = yield ws.read_message()
        self.assertEqual(test_str, response,
                         "Server did not send {0}, instead sent: {1}"
                         .format(test_str, response))

    @gen_test
    def test_error(self):
        """Test the self.send_error_msg back to the client"""
        ws = yield self.ws_connect('/error')
        test_str = 'Bad request'
        ws.write_message(test_str)
        response_str = yield ws.read_message()
        response = json.loads(response_str)
        self.assertEqual(test_str, response['_error'],
                         "Server did not send {0}, instead sent: {1}"
                         .format(test_str, response))
        self.assertIsNotNone(response['when'],
                             "Server did not send 'when' key")

    @gen_test
    def test_misconfigured_class(self):
        """This test verifies that the BaseException is thrown when you do not
        override"""
        with self.assertRaises(BaseException) as cm:
            yield self.ws_connect('/misconfigured')
            self.assertEqual(cm.exception.code, 500)


if __name__ == '__main__':
    unittest.main()
