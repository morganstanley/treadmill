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
        subproc.load_packages(aliases.split(':'))
        for exe in subproc.get_aliases():
            success = True
            fullpath = subproc.resolve(exe)
            if fullpath:
                print('{:<30}{:<10}{}'.format(exe, 'ok', fullpath))
            else:
                print('{:<30}{:<10}'.format(exe, 'fail'))

    return check
