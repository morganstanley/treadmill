"""Checkout cell capacity.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill.checkout import capacity


def init():
    """Top level command handler."""

    @click.command('capacity')
    def check_capacity():
        """Check cell capacity."""
        return capacity.test

    return check_capacity
