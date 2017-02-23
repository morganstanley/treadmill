"""
Treadmill REST base module
"""
from __future__ import absolute_import

import abc
import logging
import importlib
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi
import tornado.netutil

import flask


FLASK_APP = flask.Flask(__name__)
FLASK_APP.config['BUNDLE_ERRORS'] = True

_LOGGER = logging.getLogger(__name__)


class RestServer(object):
    """REST Server."""

    @abc.abstractmethod
    def _setup_auth(self):
        """Setup the http authentication."""
        pass

    @abc.abstractmethod
    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint."""
        pass

    def run(self):
        """Start server."""
        self._setup_auth()

        FLASK_APP.config['REST_SERVER'] = self

        container = tornado.wsgi.WSGIContainer(FLASK_APP)
        http_server = tornado.httpserver.HTTPServer(container)

        self._setup_endpoint(http_server)

        tornado.ioloop.IOLoop.current().start()


class TcpRestServer(RestServer):
    """TCP based REST Server."""

    def __init__(self, port, host='0.0.0.0', auth_type=None, protect=None):
        """Init method."""
        self.port = int(port)
        self.host = host
        self.auth_type = auth_type
        self.protect = protect

    def _setup_auth(self):
        """Setup the http authentication."""
        if self.auth_type is not None:
            _LOGGER.info('Starting REST server: %s:%s, auth: %s, protect: %r',
                         self.host, self.port, self.auth_type, self.protect)
            try:
                mod = importlib.import_module(
                    'treadmill.plugins.rest.auth.' + self.auth_type)
                FLASK_APP.wsgi_app = mod.wrap(FLASK_APP.wsgi_app, self.protect)
            except:
                _LOGGER.exception('Unable to load auth plugin.')
                raise
        else:
            _LOGGER.info('Starting REST (noauth) server on %s:%i',
                         self.host, self.port)

    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint."""
        http_server.listen(self.port)


class UdsRestServer(RestServer):
    """UNIX domain socket based REST Server."""

    def __init__(self, socket):
        """Init method."""
        self.socket = socket

    def _setup_auth(self):
        """Setup the http authentication."""
        _LOGGER.info('Starting REST (noauth) server on %s', self.socket)

    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint."""
        unix_socket = tornado.netutil.bind_unix_socket(self.socket)
        http_server.add_socket(unix_socket)
