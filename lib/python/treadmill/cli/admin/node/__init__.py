"""Implementation of treadmill admin node related CLI plugin.
"""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

import click

from treadmill import cli


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.option('--aliases-path', required=False,
                  envvar='TREADMILL_ALIASES_PATH',
                  help='Colon separated command alias paths')
    def node_group(aliases_path):
        """Manage Treadmill node data"""
        if aliases_path:
            os.environ['TREADMILL_ALIASES_PATH'] = aliases_path

    return node_group
