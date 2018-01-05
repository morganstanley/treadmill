"""Treadmill app-dns daemon.

Syncronizes DNS with local mirror of Zookeeper data.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import time

import click

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.zksync import utils as zksync_utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import dns_sync

_LOGGER = logging.getLogger(__name__)


def init():
    """Treadmill App DNS"""

    @click.command(name='app-dns')
    @click.option('--fs-root',
                  help='Root file system directory to zk2fs',
                  required=True)
    @click.option('--scopes', help='List of cell DNS scopes.', type=cli.DICT)
    @click.option('--no-lock', is_flag=True, default=False,
                  help='Run without lock.')
    def appdns(fs_root, scopes, no_lock):
        """Start Treadmill App DNS"""
        cell = context.GLOBAL.cell
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

        cell_obj = admin_cell.get(cell)
        _LOGGER.debug('cell_obj: %r', cell_obj)

        location = cell_obj.get('location')
        if not location:
            cli.bad_exit('Cell location needs to be set to lookup "closest" '
                         'DNS server')

        region, campus = location.split('.')

        if not scopes:
            scopes = {}

        if 'region' not in scopes:
            scopes['region'] = region

        if 'campus' not in scopes:
            scopes['campus'] = campus

        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        dns_entries = admin_dns.list({'location': location})

        if not dns_entries:
            dns_entries = admin_dns.list({'location': '{0}*'.format(region)})

        if not dns_entries:
            cli.bad_exit('No DNS entries for this cell location %s' % region)

        # For now, just grab the first one, will support multiple later
        dyndns_servers = dns_entries[0]['rest-server']
        fqdn = dns_entries[0]['fqdn']

        # keep sleeping until zksync ready
        modified = zksync_utils.wait_for_ready(fs_root)

        masters = [master['hostname'] for master in cell_obj['masters']]
        sync = dns_sync.DnsSync(cell,
                                dyndns_servers,
                                fqdn,
                                fs_root,
                                scopes,
                                masters)

        def _run():
            """Run sync process."""
            modified_at = 0
            while True:
                new_modified = os.stat(modified).st_mtime
                if new_modified > modified_at:
                    sync.sync()
                    modified_at = new_modified

                time.sleep(5)

        if not no_lock:
            lock = zkutils.make_lock(context.GLOBAL.zk.conn,
                                     z.path.election(__name__))

            _LOGGER.info('Waiting for leader lock.')
            with lock:
                _run()
        else:
            _LOGGER.info('Running without lock.')
            _run()

    return appdns
