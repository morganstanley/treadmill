"""Checkout cell servers."""
from __future__ import absolute_import

import click

from treadmill.tests import servers


def init():
    """Top level command handler."""

    @click.command('servers')
    def check_servers():
        """Checkout nodeinfo API."""
        return servers.test

    return check_servers
