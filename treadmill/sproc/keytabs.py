"""Runs Treadmill keytab locker service."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time
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
        """Manage Kerberos keytabs."""
        pass

    @top.command()
    @click.option('--kt-spool-dir',
                  help='Keytab spool directory.')
    def locker(kt_spool_dir):
        """Run keytab locker daemon."""
        kt_locker = keytabs.KeytabLocker(context.GLOBAL.zk.conn, kt_spool_dir)
        keytabs.run_server(kt_locker)

    @top.command()
    @click.option('--kt-spool-dir',
                  help='Keytab spool directory.')
    @click.option('--host-kt', help='Path to host keytab',
                  default='/etc/krb5.keytab')
    @click.option('--refresh-interval', type=int,
                  default=_KT_REFRESH_INTERVAL)
    def make(kt_spool_dir, host_kt, refresh_interval):
        """Periodically refresh keytabs on the node."""
        while True:
            keytabs.make_keytab(
                context.GLOBAL.zk.conn,
                kt_spool_dir,
                host_kt=host_kt)

            time.sleep(refresh_interval)

    del make
    del locker
    return top
