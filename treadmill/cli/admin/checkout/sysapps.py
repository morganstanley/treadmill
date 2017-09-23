"""Checkout cell sysapps.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill.checkout import sysapps


def init():
    """Top level command handler."""

    @click.command('sysapps')
    def check_sysapps():
        """Checkout system apps health."""
        return sysapps.test

    return check_sysapps
