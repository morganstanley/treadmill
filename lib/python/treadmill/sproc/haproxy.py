"""
Treadmill HAProxy system process
"""
from __future__ import absolute_import

import logging
import os
import time

import click

from treadmill import subproc

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
        modified = os.path.join(fs_root, '.modified')
        while not os.path.exists(modified):
            _LOGGER.info('zk2fs mirror does not exist, waiting.')
            time.sleep(1)

        # TODO: implment config creation by iterating over fs-root/app-groups.
        # We would get all app-groups, then add a frontend and backend for
        # each lbendpoint for this cell's region. Of course this would be
        # abstracted into treamdill.haproxy.

        subproc.safe_exec(['haproxy', '-f', config])

    return haproxy
