"""Checkout Zookeeper ensemble."""
from __future__ import absolute_import

import click

from treadmill.tests import capacity


def init():
    """Top level command handler."""

    @click.command('capacity')
    def check_capacity():
        """Check cell capacity."""
        return capacity.test

    return check_capacity
