"""REST request rate limit decorators module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import flask

import flask_limiter
from flask_limiter import util


def _get_key_func(limit_by=None):
    """Get limit key factory function."""

    def generate_limit_key():
        """Generate key for request rate limiting."""
        # use authenticated user if specified, otherwise use ip by default
        if limit_by == 'user' and flask.g.get('user') is not None:
            return flask.g.get('user')
        return util.get_remote_address()

    return generate_limit_key


def wrap(app, rule):
    """Wrap flask app with rule based request rate control.
    """
    limit_by = rule.pop('_limit_by', None)
    limiter = flask_limiter.Limiter(
        app,
        key_func=_get_key_func(limit_by=limit_by),
    )

    limit_value = rule.pop('_global', None)
    if limit_value is not None:
        decorator = limiter.shared_limit(limit_value, scope='_global')
        for endpoint, func in app.view_functions.items():
            # A shared rate limit could be evaluated multiple times for single
            # request, because `flask_limiter` uses
            # "func.__module__ + func.__name__" as key format to differentiate
            # non Blueprint routes.
            #
            # For example, both cases blow register to the same key format as
            # "flask.helpers.send_static_file"
            # 1. `restful_plus` static file requests (i.e. "/swaggerui/ui.js").
            # 2. default static file endpoint registration of
            # `treadmill.rest.FLASK_APP`, because param "static_folder" in
            # constructer has its default value.
            #
            # so each request of hitting "flask.helpers.send_static_file" will
            # increase rate limit counter by 2 (which 1 is expectation). A
            # workaround here is only concerning about `treadmill.rest.api`
            # resources.
            if hasattr(func, 'view_class'):
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
