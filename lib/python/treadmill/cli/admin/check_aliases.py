"""Check aliases.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import subproc


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.argument('aliases')
    def check(aliases):
        """Check aliases."""
        exes = subproc.get_aliases(aliases)
        for exe in exes:
            success = True
            try:
                fullpath = subproc.resolve(exe)
                print('{:<30}{:<10}{}'.format(exe, 'ok', fullpath))
            except subproc.CommandAliasError:
                print('{:<30}{:<10}'.format(exe, 'fail'))

    return check
