"""Implementation of treadmill admin diag related CLI plugin.
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
    @click.pass_context
    def run(_ctxp):
        """Manage Local node and container diagnostics.
        """

    return run
