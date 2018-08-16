"""Admin Cell CLI module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import admin
from treadmill import cli
from treadmill import context

_LOGGER = logging.getLogger(__name__)


class CellCtx():
    """Cell context."""

    def __init__(self, realm, version, treadmill_root=None):
        self.cell = context.GLOBAL.cell
        self.realm = realm

        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(self.cell)
        location_cells = admin_cell.list({'location': cell['location']})

        self.version = cell['version']
        if version:
            self.version = version
        self.proid = cell['username']
        self.treadmill = cell.get('root')
        self.data = cell.get('data')

        if not self.treadmill:
            self.treadmill = treadmill_root

        self.location = cell['location']
        self.location_cells = [cell['_id'] for cell in location_cells]


def init():
    """Admin Cell CLI module"""

    @click.group(cls=cli.make_commands(__name__))
    @click.option('--realm', help='Master kerberos realm',
                  required=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--root', required=False,
                  envvar='TREADMILL_ROOT', help='Treadmill root path')
    @click.option('--version', help='Override the version in LDAP')
    @click.pass_context
    def cell_grp(ctx, realm, root, version):
        """Manage treadmill cell."""
        ctx.obj = CellCtx(realm, version, root)

    return cell_grp
