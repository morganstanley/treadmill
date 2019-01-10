"""REST request rate limit decorators module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask_limiter
import flask_limiter.util


def wrap(app, rule):
    """Wrap flask app with rule based request rate control.
    """
    limiter = flask_limiter.Limiter(
        app,
        key_func=flask_limiter.util.get_remote_address,
    )
    decorator = limiter.shared_limit(rule, '_global')

    for endpoint, func in app.view_functions.items():
        app.view_functions[endpoint] = decorator(func)

    return app
