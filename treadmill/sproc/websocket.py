"""
Treadmill Websocket server.
"""


import logging
import os
import time
import tornado.httpserver
import tornado.ioloop
import tornado.web

import click

from treadmill import cli
from treadmill import websocket as ws
from treadmill.websocket import api


_LOGGER = logging.getLogger(__name__)


def init():
    """Treadmill Websocket"""

    @click.command()
    @click.option('--fs-root',
                  help='Root file system directory to zk2fs',
                  required=True)
    @click.option('-m', '--modules', help='API modules to load.',
                  required=True, type=cli.LIST)
    @click.option('--port',
                  help='Websocket HTTP port',
                  required=True, default=8080)
    def websocket(fs_root, modules, port):
        """Treadmill Websocket"""
        _LOGGER.debug('port: %s', port)

        modified = os.path.join(fs_root, '.modified')
        while not os.path.exists(modified):
            _LOGGER.info('zk2fs mirror does not exist, waiting.')
            time.sleep(1)

        pubsub = ws.DirWatchPubSub(fs_root)
        for topic, impl in api.init(modules):
            pubsub.impl[topic] = impl

        pubsub.run_detached()
        application = tornado.web.Application([(r'/', pubsub.ws)])

        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    return websocket
