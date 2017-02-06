"""
Treadmill REST base module
"""


import logging
import importlib
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi

import flask


FLASK_APP = flask.Flask(__name__)
FLASK_APP.config['BUNDLE_ERRORS'] = True

_LOGGER = logging.getLogger(__name__)


class RestServer(object):
    """REST Server"""

    def __init__(self, port, host='0.0.0.0'):
        """init method"""
        self.port = int(port)
        self.host = host

    def run(self, auth_type=None, protect=None):
        """Start server"""
        if auth_type is not None:
            _LOGGER.info('Starting REST server: %s:%s, auth: %s, protect: %r',
                         self.host, self.port, auth_type, protect)
            try:
                mod = importlib.import_module(
                    'treadmill.plugins.rest.auth.' + auth_type)
                FLASK_APP.wsgi_app = mod.wrap(FLASK_APP.wsgi_app, protect)
            except:
                _LOGGER.exception('Unable to load auth plugin.')
                raise
        else:
            _LOGGER.info('Starting REST (noauth) server on %s:%i',
                         self.host, self.port)

        FLASK_APP.config['REST_SERVER'] = self

        container = tornado.wsgi.WSGIContainer(FLASK_APP)
        http_server = tornado.httpserver.HTTPServer(container)
        http_server.listen(self.port)
        tornado.ioloop.IOLoop.current().start()
