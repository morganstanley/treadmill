"""Implementation of treadmill admin ldap CLI init plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli
from treadmill import context


def init():
    """Init LDAP CLI group"""

    # Disable redeginig name 'init' warning.
    #
    # pylint: disable=W0621
    @click.command(name='init')
    @cli.admin.ON_EXCEPTIONS
    def _init():
        """Initializes the LDAP directory structure"""
        return context.GLOBAL.admin.conn.init()

    return _init
