"""Checkout cell sysapps."""

import click

from treadmill.checkout import sysapps


def init():
    """Top level command handler."""

    @click.command('sysapps')
    def check_sysapps():
        """Checkout system apps health."""
        return sysapps.test

    return check_sysapps
