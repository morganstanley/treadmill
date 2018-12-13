"""Admin Cell CLI module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import cli
from treadmill import context

_LOGGER = logging.getLogger(__name__)


def init():
    """Admin Cell CLI module"""

    @click.group(
        cls=cli.make_commands(
            __name__ + '.' + context.GLOBAL.get_profile_name()
        )
    )
    @click.option(
        '--cell', required=True,
        envvar='TREADMILL_CELL',
        is_eager=True, callback=cli.handle_context_opt,
        expose_value=False
    )
    def cell_grp():
        """Manage treadmill cell.
        """

    return cell_grp
