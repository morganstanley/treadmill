"""Kerberos related CLI tools.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pkgutil
import click

from treadmill import cli

__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.pass_context
    def run(_ctxp):
        """Manage Kerberos tickets."""

    return run
