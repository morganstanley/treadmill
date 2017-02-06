"""Admin Cell CLI module"""


import logging

import click

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import utils
from treadmill import versionmgr
from treadmill import zkutils
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def init():
    """Admin Cell CLI module"""

    @click.command()
    @click.option('--ldap', required=True, envvar='TREADMILL_LDAP')
    @click.option('--ldap-search-base', required=True,
                  envvar='TREADMILL_LDAP_SEARCH_BASE')
    @click.option('--batch', help='Upgrade batch size.',
                  type=int, default=10)
    @click.option('--timeout', help='Upgrade timeout.',
                  type=int, default=60)
    @click.option('--treadmill_root', help='Treadmill root dir.')
    @click.option('--continue_on_error',
                  help='Stop if batch upgrade failed.',
                  is_flag=True, default=False)
    @click.option('--dry_run',
                  help='Dry run, verify status.',
                  is_flag=True, default=False)
    @click.option('--force',
                  help='Force event if server appears up-to-date',
                  is_flag=True, default=False)
    @click.option('--servers', help='Servers to upgrade.',
                  multiple=True, default=[],)
    @click.argument('cell')
    @cli.admin.ON_EXCEPTIONS
    def upgrade(cell, ldap, ldap_search_base, batch, timeout, treadmill_root,
                continue_on_error, dry_run, force, servers):
        """Upgrade the supplied cell"""
        context.GLOBAL.ldap.url = ldap
        context.GLOBAL.ldap.search_base = ldap_search_base

        servers = []
        for server_list in servers:
            servers.extend(server_list.split(','))

        if not treadmill_root:
            admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
            cell_info = admin_cell.get(cell)
            treadmill_root = cell_info.get('treadmill_root')

        _LOGGER.info('Treadmill root: %s', treadmill_root)
        digest = versionmgr.checksum_dir(treadmill_root).hexdigest()
        _LOGGER.info('Checksum: %s', digest)

        context.GLOBAL.resolve(cell)
        zkclient = context.GLOBAL.zk.conn

        if not servers:
            # pylint: disable=R0204
            servers = zkutils.get(zkclient, z.SERVERS)

        if dry_run:
            failed = versionmgr.verify(zkclient, digest, servers)
        else:
            failed = versionmgr.upgrade(
                zkclient,
                digest, servers,
                batch,
                timeout,
                stop_on_error=(not continue_on_error),
                force_upgrade=force,
            )

        if not failed:
            _LOGGER.info('All servers are up to date.')
        else:
            _LOGGER.error('Upgrade failed.')

        utils.print_yaml(failed)

    return upgrade
