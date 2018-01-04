"""Manage Treadmill / lbcontrol integration.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import time

import click

from treadmill import cli
from treadmill.zksync import utils as zks_utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms.lbvirtual import app_watch


_STEP_TIMEOUT = 5

_LOGGER = logging.getLogger(__name__)


def init():
    """App main."""

    @click.command()
    @click.option('--fs-root', help='Path that mirrors Zookeeper data.',
                  type=click.Path(exists=True), required=True)
    @click.option('--partition', help='LBVirtual partition',
                  type=int, required=True,
                  envvar='TREADMILL_IDENTITY')
    @click.option('--total-partitions', help='LBVirtual total partitions',
                  type=int, required=True)
    @click.option('--lbenv', help='LBControl environment',
                  default='prod')
    @click.option('--watch-cells', help='List of cells to watch',
                  type=cli.LIST, required=True)
    @click.option('--watch-groups', help='List of app groups to watch',
                  type=cli.LIST, required=True)
    def lbvirtual(fs_root, partition, total_partitions, lbenv,
                  watch_cells, watch_groups):
        """Syncronizes LB virtuals with apps/instances on the watched cells."""

        # keep sleeping until zksync ready
        for cell in watch_cells:
            _LOGGER.info('Waiting for %r zk2fs mirrors to be ready.', cell)
            zks_utils.wait_for_ready(os.path.join(fs_root, cell))

        lbenv = 'PROD' if lbenv.upper() == 'PROD' else 'QA'
        lbc = lbcontrol.LBControl2(lbenv)

        _LOGGER.info('Starting LBVirtual, partition: %s, total_partitions: %s',
                     partition, total_partitions)
        virtual_app_watch = app_watch.VirtualAppWatch(
            lbc, fs_root, partition, total_partitions,
            watch_cells, watch_groups
        )

        while True:
            try:
                start_time = time.time()
                virtual_app_watch.sync()
                _LOGGER.info('Sync time: %s', time.time() - start_time)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Sync error')

            time.sleep(_STEP_TIMEOUT)

    return lbvirtual
