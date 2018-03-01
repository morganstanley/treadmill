"""Collect node information post crash.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import postmortem

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--treadmill-root', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True,
                  help='Treadmill root path.')
    def collect(treadmill_root):
        """Collect Treadmill node data"""
        postmortem.run(treadmill_root)

    return collect
