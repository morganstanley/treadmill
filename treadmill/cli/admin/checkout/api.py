"""Checkout cell api."""

import click

from treadmill.checkout import api


def init():
    """Top level command handler."""

    @click.command('api')
    def check_api():
        """Checkout API."""
        return api.test

    return check_api
