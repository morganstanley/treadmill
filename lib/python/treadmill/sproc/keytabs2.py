"""Runs Treadmill keytab locker service. This is a upgraded version from
`treadmill.sproc.keytabs` which supports requesting by SPNs and relevant
ownership.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import context
from treadmill import keytabs2


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.group()
    def top():
        """Manage Kerberos keytabs.
        """

    @top.command()
    @click.option('--kt-spool-dir',
                  help='Keytab spool directory.')
    @click.option('--approot',
                  type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT',
                  required=True)
    @click.option('--appname',
                  help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint',
                  help='Pseudo endpoint to use for discovery',
                  default='keytabs-v2')
    @click.option('-p', '--port',
                  help='Keytab locker server port.',
                  default=0)
    @click.option('--database',
                  required=True,
                  type=click.Path(exists=True, readable=True),
                  help='SQLite3 db file stores VIP keytab/proid relations.')
    def locker(kt_spool_dir, approot, appname, endpoint, port, database):
        """Run keytab locker daemon."""
        kt_locker = keytabs2.KeytabLocker(context.GLOBAL.zk.conn, kt_spool_dir)
        kt_server = keytabs2.get_listening_server(kt_locker, port)

        # TODO: refator this as an untility function
        from treadmill.sproc.keytabs import create_endpoint_file

        port = kt_server.get_actual_port()
        create_endpoint_file(approot, port, appname, endpoint)
        keytabs2.ensure_table_exists(database)

        _LOGGER.info('Starting keytab locker server on port: %s', port)
        kt_server.run()

    del locker
    return top
