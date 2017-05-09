"""
Authentication plugin.
"""


def wrap(wsgi_app, protect):
    """Wrap FLASK app for custom authentication."""
    del protect
    return wsgi_app
