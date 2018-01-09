"""Treadmill Websocket server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import tornado.httpserver
import tornado.ioloop
import tornado.web

import click

from treadmill import cli
from treadmill import websocket as ws
from treadmill.websocket import api
from treadmill.zksync import utils as zksync_utils


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

        # keep sleeping until zksync ready
        zksync_utils.wait_for_ready(fs_root)

        impl, watches = {}, []
        for topic, topic_impl, topic_watches in api.init(modules):
            impl[topic] = topic_impl
            watches.extend(topic_watches)

        pubsub = ws.DirWatchPubSub(fs_root, impl, watches)
        pubsub.run_detached()

        application = tornado.web.Application([(r'/', pubsub.ws)])
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    return websocket
