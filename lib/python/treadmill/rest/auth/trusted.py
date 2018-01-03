"""Wsgi wrapper to extract 'whoami' header and set as auth user.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

_LOGGER = logging.getLogger(__name__)


class Trusted(object):
    """Trusted WSGI wrapper.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        """Wraps app response.
        """
        environ['REMOTE_USER'] = environ.get('HTTP_X_TREADMILL_TRUSTED_AGENT')
        _LOGGER.info('Setting trusted user: %s', environ['REMOTE_USER'])
        return self.app(environ, start_response)


def wrap(app, *_args, **_kwargs):
    """Wrap wsgi app.
    """
    return Trusted(app)
