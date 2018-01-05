"""Checkout sysapps version.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms.checkout import cell_version


def init():
    """Top level command handler."""

    @click.command('dns')
    def check_cell_version():
        """Checkout system apps version."""
        return cell_version.test

    return check_cell_version
