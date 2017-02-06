"""Exec command in Treadmill sproc environment."""


import os
import logging

import click

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command(name='exec')
    @click.argument('cmd', nargs=-1)
    def exec_cmd(cmd):
        """Exec command line in treadmill environment."""
        args = list(cmd)
        print(args)
        _LOGGER.info('execvp: %s, %r', args[0], args)
        os.execvp(args[0], args)

    return exec_cmd
