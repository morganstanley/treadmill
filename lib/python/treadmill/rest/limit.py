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

    limit_value = rule.pop('_global', None)
    if limit_value is not None:
        decorator = limiter.shared_limit(limit_value, scope='_global')
        for endpoint, func in app.view_functions.items():
            app.view_functions[endpoint] = decorator(func)

    if rule:
        decorators = {
            module: limiter.shared_limit(limit_value, scope=module)
            for module, limit_value in rule.items()
        }

        for endpoint, func in app.view_functions.items():

            module = None
            if hasattr(func, 'view_class'):
                module = func.__module__.rsplit('.')[-1]

            if module in decorators:
                decorator = decorators[module]
                app.view_functions[endpoint] = decorator(func)

    return app
