"""Wsgi wrapper to extract 'whoami' header and set as auth user.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import urllib.parse

_LOGGER = logging.getLogger(__name__)


class Trusted:
    """Trusted WSGI wrapper.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        """Wraps app response.
        """
        environ['REMOTE_USER'] = environ.get('HTTP_X_TREADMILL_TRUSTED_AGENT')

        # TODO: this is hack.
        #
        #       Seems like tornado does not parse http+unix urls correctly.
        #       It tries to urldecode it, and by doing so it will decode socket
        #       path, with is not part of the path.
        #
        #       Consider url:
        #       http+unix://%2Ftmp%2Fsock.sock/a/b/c
        #
        #       It will be decoded to:
        #       http+unix///tmp/sock.sock/a/b/c
        #
        #       At this point, it will be used as PATH_INFO, and result will be
        #       "resource not found" error.
        #
        #       Until this is fixed:
        #       - get 'SERVER_NAME': ('%2Ftmp%2Fsock.sock')
        #       - decode
        #       - if starts with http+unix://<decoded> - strip for path.
        path = environ.get('PATH_INFO')
        if path and path.startswith('http+unix://'):
            server = environ.get('SERVER_NAME')
            _LOGGER.info('PATH_INFO: %s, SERVER: %s', path, server)
            if server:
                strip = 'http+unix://{}'.format(urllib.parse.unquote(server))
                if path.startswith(strip):
                    correct_path = path[len(strip):]
                    _LOGGER.info('Reconfiguring PATH_INFO: %s', correct_path)
                    environ['PATH_INFO'] = correct_path

        _LOGGER.info('Setting trusted user: %s', environ['REMOTE_USER'])
        return self.app(environ, start_response)


def wrap(app, *_args, **_kwargs):
    """Wrap wsgi app.
    """
    return Trusted(app)
