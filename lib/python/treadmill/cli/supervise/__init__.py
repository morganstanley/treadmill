"""Distributed supervision suite.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    def run():
        """Cross-cell supervision tools."""
        cli.init_logger('daemon.json')

    return run
