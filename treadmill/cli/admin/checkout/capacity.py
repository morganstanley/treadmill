"""Checkout Zookeeper ensemble."""

import click

from treadmill.checkout import capacity


def init():
    """Top level command handler."""

    @click.command('capacity')
    def check_capacity():
        """Check cell capacity."""
        return capacity.test

    return check_capacity
