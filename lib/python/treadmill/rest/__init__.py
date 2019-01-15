"""Treadmill REST base module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging
import os
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi
import tornado.netutil

import flask

from treadmill import fs
from treadmill import plugin_manager


FLASK_APP = flask.Flask(__name__)
FLASK_APP.config['BUNDLE_ERRORS'] = True

_LOGGER = logging.getLogger(__name__)


class CompliantJsonEncoder(flask.json.JSONEncoder):
    """A JSONEncoder that forces NaN and Infinity into null values.

    The Python community takes the view that NaN and Infinity in JSON are
    a widespread extension of the standard, but decoders built into the
    browsers unanimously reject this. We need an encoder with defaults that
    play well with browsers.
    """
    def __init__(self, *args, **kwargs):
        if 'ignore_nan' in kwargs:
            del kwargs['ignore_nan']

        super(CompliantJsonEncoder, self).__init__(
            ignore_nan=True, *args, **kwargs
        )


FLASK_APP.json_encoder = CompliantJsonEncoder


class RestServer:
    """REST Server."""

    @abc.abstractmethod
    def _setup_auth(self):
        """Setup the http authentication.
        """

    @abc.abstractmethod
    def _setup_rate_limit(self):
        """Setup the http request rate limit control.
        """

    @abc.abstractmethod
    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint.
        """

    def run(self):
        """Start server."""
        self._setup_rate_limit()
        self._setup_auth()

        FLASK_APP.config['REST_SERVER'] = self

        container = tornado.wsgi.WSGIContainer(FLASK_APP)
        http_server = tornado.httpserver.HTTPServer(container)

        self._setup_endpoint(http_server)

        tornado.ioloop.IOLoop.current().start()


class TcpRestServer(RestServer):
    """TCP based REST Server."""

    def __init__(self, port, host='0.0.0.0', auth_type=None, protect=None,
                 workers=1, backlog=128, rate_limit=None):
        """Init methods

        :param int port: port number to listen on (required)
        :param str host: host IP to listen on, default is '0.0.0.0'
        :param str auth_type: the auth type, default is None
        :param str protect: which URLs to protect, default is None
        :param int workers: the number of workers to be forked, default is 1
        :param int backlog: the connection backlog, default is 128
        :param dict rate_limit: API request rate limit rule, default is None
        """
        self.port = int(port)
        self.host = host
        self.auth_type = auth_type
        self.protect = protect
        self.workers = workers
        self.backlog = backlog
        self.rate_limit = rate_limit

    def _setup_rate_limit(self):
        """Setup the http request rate limit control."""
        if self.rate_limit is not None:
            _LOGGER.info('Starting REST (rate limit: %s) server on %s:%i',
                         self.rate_limit, self.host, self.port)
            try:
                limit = plugin_manager.load('treadmill.rest', 'limit')
                limit.wrap(FLASK_APP, self.rate_limit)
            except Exception:
                _LOGGER.exception('Unable to setup rate limit.')
                raise
        else:
            _LOGGER.info('Starting REST (no rate limit) server on %s:%i',
                         self.host, self.port)

    def _setup_auth(self):
        """Setup the http authentication."""
        if self.auth_type is not None:
            _LOGGER.info('Starting REST server: %s:%s, auth: %s, protect: %r',
                         self.host, self.port, self.auth_type, self.protect)
            try:
                auth = plugin_manager.load('treadmill.rest.authentication',
                                           self.auth_type)
                FLASK_APP.wsgi_app = auth.wrap(FLASK_APP.wsgi_app,
                                               self.protect)
            except KeyError:
                _LOGGER.error('Unsupported auth type: %s', self.auth_type)
                raise
            except Exception:
                _LOGGER.exception('Unable to load auth plugin.')
                raise
        else:
            _LOGGER.info('Starting REST (noauth) server on %s:%i',
                         self.host, self.port)

    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint."""
        http_server.bind(self.port, backlog=self.backlog)
        http_server.start(self.workers)


class UdsRestServer(RestServer):
    """UNIX domain socket based REST Server."""

    def __init__(self, socket, auth_type=None, workers=1, backlog=128):
        """Init method."""
        self.socket = socket
        self.auth_type = auth_type
        self.workers = workers
        self.backlog = backlog

    def _setup_rate_limit(self):
        """Setup the http request rate limit control.
        """

    def _setup_auth(self):
        """Setup the http authentication."""
        if self.auth_type is not None:
            _LOGGER.info('Starting REST server: %s, auth: %s',
                         self.socket, self.auth_type)
            try:
                auth = plugin_manager.load('treadmill.rest.authentication',
                                           self.auth_type)
                FLASK_APP.wsgi_app = auth.wrap(FLASK_APP.wsgi_app)
            except KeyError:
                _LOGGER.error('Unsupported auth type: %s', self.auth_type)
                raise
            except Exception:
                _LOGGER.exception('Unable to load auth plugin.')
                raise

        else:
            _LOGGER.info('Starting REST (noauth) server on %s', self.socket)

    def _setup_endpoint(self, http_server):
        """Setup the http server endpoint."""
        fs.mkdir_safe(os.path.dirname(self.socket), mode=0o755)
        unix_socket = tornado.netutil.bind_unix_socket(self.socket,
                                                       backlog=self.backlog)
        if self.workers != 1:
            tornado.process.fork_processes(self.workers)

        http_server.add_socket(unix_socket)
