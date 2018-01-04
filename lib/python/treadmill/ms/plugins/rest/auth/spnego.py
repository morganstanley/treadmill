"""Webauthd/spnego auth plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import webauthd_wsgi as webauthd


_LOGGER = logging.getLogger(__name__)


def wrap(wsgi_app, protect):
    """Wrap FLASK app in webauthd middleware."""
    _LOGGER.info('Loading spnego auth.')

    unprotected_paths = ['/']
    unprotected_methods = ['OPTIONS']
    protected_paths = []

    if protect:
        protected_paths.extend(protect)

    app = webauthd.make_middleware(wsgi_app,
                                   auth_type='spnego',
                                   auth_data={},
                                   protected_paths=protected_paths,
                                   unprotected_paths=unprotected_paths,
                                   unprotected_methods=unprotected_methods,
                                   wad_cnx_settings=None)

    return app
