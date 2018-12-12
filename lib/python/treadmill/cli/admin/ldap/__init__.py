"""Implementation of treadmill admin ldap CLI plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli


def init():
    """Return top level command handler"""

    @click.group(cls=cli.make_commands(__name__))
    def ldap():
        """Manage Treadmill LDAP data.
        """

    return ldap
