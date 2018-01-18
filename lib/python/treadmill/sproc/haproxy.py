"""Treadmill HAProxy system process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import subproc
from treadmill.zksync import utils as zksync_utils

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--fs-root',
                  help='Root file system directory to zk2fs',
                  required=True)
    @click.option('--config',
                  help='HAProxy config file',
                  required=True, )
    def haproxy(fs_root, config):
        """Run Treadmill HAProxy"""
        # keep sleeping until zksync ready
        zksync_utils.wait_for_ready(fs_root)

        # TODO: implment config creation by iterating over fs-root/app-groups.
        # We would get all app-groups, then add a frontend and backend for
        # each lbendpoint for this cell's region. Of course this would be
        # abstracted into treamdill.haproxy.

        subproc.safe_exec(['haproxy', '-f', config])

    return haproxy
