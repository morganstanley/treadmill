"""Helper class to disable proxy for given call."""

import os


# TODO: this code need to be moved into core.
class NoProxy():
    """Safely remove/restore proxy environment variables."""

    def __init__(self):
        self.saved = dict()

    def __enter__(self):
        for key in list(os.environ.keys()):
            if key.lower().endswith('_proxy'):
                self.saved[key] = os.environ[key]
                del os.environ[key]

    def __exit__(self, *args, **kwargs):
        for key, value in self.saved.items():
            os.environ[key] = value


def noproxy(func):
    """Disable proxy decorator."""

    def _no_proxy(*args, **kwargs):
        """Wrapper function."""
        with NoProxy() as _:
            return func(*args, **kwargs)

    return _no_proxy
