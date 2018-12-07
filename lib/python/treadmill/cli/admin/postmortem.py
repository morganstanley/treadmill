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
    @click.option('--root-cgroup', default='treadmill',
                  envvar='TREADMILL_ROOT_CGROUP', required=False)
    def collect(treadmill_root, root_cgroup):
        """Collect Treadmill node data"""
        postmortem.run(treadmill_root, root_cgroup)

    return collect
