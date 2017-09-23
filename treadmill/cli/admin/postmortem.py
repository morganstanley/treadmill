"""Collect node information post crash.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import postmortem

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--treadmill-root', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True,
                  help='Treadmill root path.')
    @click.option('--upload-user',
                  envvar='TREADMILL_ID', required=True,
                  help='Upload postmortem statistics with this user.')
    @click.option('--upload-url',
                  help='Upload postmortem statistics to this file url.')
    def collect(treadmill_root, upload_user, upload_url):
        """Collect Treadmill node data"""
        os.environ['TREADMILL_ID'] = upload_user
        postmortem.run(treadmill_root, upload_url)

    return collect
