"""Implementation of treadmill admin ldap CLI app_group plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from treadmill.admin import exc as admin_exceptions

from treadmill import cli
from treadmill import context

_LOGGER = logging.getLogger(__name__)


def init():  # pylint: disable=R0912

    """Configures App Groups"""
    formatter = cli.make_formatter('appgroup')

    @click.group()
    def app_group():  # pylint: disable=W0621
        """Manage App Groups.
        """

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--group-type', help='App group type',
                  required=False)
    @click.option('--cell', help='Cell app pattern could be in; comma '
                  'separated list of cells', type=cli.LIST)
    @click.option('--pattern', help='App pattern')
    @click.option('--endpoints',
                  help='App group endpoints, comma separated list.',
                  type=cli.LIST)
    @click.option('--data', help='App group specific data as key=value '
                  'comma separated list', type=cli.LIST)
    def configure(name, group_type, cell, pattern, endpoints, data):
        """Create, get or modify an App Group"""
        admin_app_group = context.GLOBAL.admin.app_group()

        data_struct = {}
        if group_type:
            data_struct['group-type'] = group_type
        if cell:
            data_struct['cells'] = cell
        if pattern is not None:
            data_struct['pattern'] = pattern
        if data is not None:
            data_struct['data'] = data
        if endpoints is not None:
            data_struct['endpoints'] = endpoints

        if data_struct:
            try:
                admin_app_group.create(name, data_struct)
                _LOGGER.debug('Created app group %s', name)
            except admin_exceptions.AlreadyExistsResult:
                _LOGGER.debug('Updating app group %s', name)
                admin_app_group.update(name, data_struct)

        try:
            cli.out(formatter(admin_app_group.get(name, dirty=True)))
        except admin_exceptions.NoSuchObjectResult:
            cli.bad_exit('App group does not exist: %s', name)

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @click.option('--add', help='Cells to to add.', type=cli.LIST)
    @click.option('--remove', help='Cells to to remove.', type=cli.LIST)
    @cli.admin.ON_EXCEPTIONS
    def cells(add, remove, name):
        """Add or remove cells from the app-group"""
        admin_app_group = context.GLOBAL.admin.app_group()
        existing = admin_app_group.get(name, dirty=bool(add or remove))
        group_cells = set(existing['cells'])

        if add:
            group_cells.update(add)
        if remove:
            group_cells = group_cells - set(remove)

        admin_app_group.update(name, {'cells': list(group_cells)})
        cli.out(formatter(admin_app_group.get(
            name, dirty=bool(add or remove)
        )))

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def get(name):
        """Get an App Group entry"""
        try:
            admin_app_group = context.GLOBAL.admin.app_group()
            cli.out(formatter(admin_app_group.get(name)))
        except admin_exceptions.NoSuchObjectResult:
            cli.bad_exit('App group does not exist: %s', name)

    @app_group.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List App Group entries"""
        admin_app_group = context.GLOBAL.admin.app_group()
        app_group_entries = admin_app_group.list({})
        cli.out(formatter(app_group_entries))

    @app_group.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def delete(name):
        """Delete an App Group entry"""
        admin_app_group = context.GLOBAL.admin.app_group()
        admin_app_group.delete(name)

    del delete
    del _list
    del get
    del cells
    del configure

    return app_group
