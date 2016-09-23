"""
Treadmill Websocket

Runs Treadmill WebSocket: this script will provide updates of application
statuses via WebSocket technology. Currently only the "state" module is
supported, i.e. "configured", "running" and "scheduled".
"""
from __future__ import absolute_import

import logging
import tornado.httpserver
import tornado.ioloop
import tornado.web

import click

from .. import discovery_wshandler
from .. import state_wshandler

_LOGGER = logging.getLogger(__name__)


def init():
    """Treadmill Websocket"""

    @click.group()
    def websocket():
        """Treadmill Websocket"""
        pass

    @websocket.command()
    @click.option('--port',
                  help='Websocket HTTP port',
                  required=True, default=8080)
    def start(port):
        """Treadmill Websocket"""
        _LOGGER.debug('port: %s', port)

        application = tornado.web.Application([
            (r'/discovery', discovery_wshandler.DiscoveryWebSocketHandler),
            (r'/state', state_wshandler.StateWebSocketHandler),
        ])

        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    del start

    return websocket
