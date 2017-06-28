"""Tests for treadmill.rest.api.*"""

import contextlib
import flask


@contextlib.contextmanager
def user_set(app, user):
    """A context manager used to fake the current user."""
    def handler(_sender, **_kwargs):
        """Store the user in flask.g."""
        flask.g.user = user
    with flask.appcontext_pushed.connected_to(handler, app):
        yield
