"""Treadmill / Active Directory (Windows) integration."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.ad import gmsa
from treadmill.zksync import utils as zksync_utils

_LOGGER = logging.getLogger(__name__)


def init():
    """App main."""

    @click.group(name='ad')
    def ad_grp():
        """Manage Active Directory integration.
        """

    @ad_grp.command(name='gmsa')
    @click.option('--fs-root', help='Path that mirrors Zookeeper data.',
                  type=click.Path(exists=True), required=True)
    @click.option('--partition', help='Windows partition', required=True)
    @click.option('--group-ou', help='AD OU where the GMSA accounts are.',
                  required=True)
    @click.option('--group-pattern', help='The group pattern to use.',
                  required=True)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def gmsa_sync(fs_root, partition, group_ou, group_pattern, no_lock):
        """Sync placements GMSA groups."""

        # keep sleeping until zksync ready
        zksync_utils.wait_for_ready(fs_root)

        watch = gmsa.HostGroupWatch(fs_root, partition, group_ou,
                                    group_pattern)
        if not no_lock:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))

            _LOGGER.info('Waiting for leader lock.')
            with lock:
                watch.run()
        else:
            _LOGGER.info('Running without lock.')
            watch.run()

    del gmsa_sync
    return ad_grp
