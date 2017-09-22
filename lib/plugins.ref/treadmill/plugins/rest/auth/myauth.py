"""
Authentication plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


def wrap(wsgi_app, protect):
    """Wrap FLASK app for custom authentication."""
    del protect
    return wsgi_app
