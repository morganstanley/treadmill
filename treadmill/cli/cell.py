"""List Treadmill cells."""


import logging

import click

from .. import cli
from treadmill import restclient
from treadmill import context

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    cell_formatter = cli.make_formatter(cli.CellPrettyFormatter)
    ctx = {}

    @click.group(name='cell')
    @click.option('--api',
                  required=False,
                  help='API url to use.',
                  envvar='TREADMILL_RESTAPI')
    def cell_grp(api):
        """List & display Treadmill cells."""
        if api:
            ctx['api'] = api

    @cell_grp.command(name='list')
    @cli.ON_REST_EXCEPTIONS
    def _list():
        """List the configured cells."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        cli.out(cell_formatter(restclient.get(restapi, '/cell/').json()))

    @cell_grp.command()
    @click.argument('name')
    @cli.ON_REST_EXCEPTIONS
    def get(name):
        """Display the details of a cell."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        cli.out(cell_formatter(restclient.get(restapi,
                                              '/cell/%s' % name).json()))

    del _list
    del get

    return cell_grp
