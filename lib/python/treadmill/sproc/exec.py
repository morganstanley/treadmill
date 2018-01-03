"""Exec command in Treadmill sproc environment.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command(name='exec')
    @click.argument('cmd', nargs=-1)
    def exec_cmd(cmd):
        """Exec command line in treadmill environment."""
        args = list(cmd)
        _LOGGER.info('execvp: %s, %r', args[0], args)
        utils.sane_execvp(args[0], args)

    return exec_cmd
