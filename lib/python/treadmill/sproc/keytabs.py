"""Runs Treadmill keytab locker service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import click

from treadmill import keytabs
from treadmill import context


_LOGGER = logging.getLogger(__name__)

# 24 hours.
_KT_REFRESH_INTERVAL = 60 * 60 * 24


def init():
    """Top level command handler."""

    @click.group()
    def top():
        """Manage Kerberos keytabs.
        """

    @top.command()
    @click.option('--kt-spool-dir',
                  help='Keytab spool directory.')
    def locker(kt_spool_dir):
        """Run keytab locker daemon."""
        kt_locker = keytabs.KeytabLocker(context.GLOBAL.zk.conn, kt_spool_dir)
        keytabs.run_server(kt_locker)

    del locker
    return top
