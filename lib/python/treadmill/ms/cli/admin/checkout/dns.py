"""Checkout DNS servers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms.checkout import dns


def init():
    """Top level command handler."""

    @click.command('dns')
    def check_dns():
        """Checkout DNS."""
        return dns.test

    return check_dns
