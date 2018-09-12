"""List Treadmill cells.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    cell_formatter = cli.make_formatter('cell')

    @click.group(name='cell')
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    def cell_grp():
        """List & display Treadmill cells."""

    @cell_grp.command(name='list')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list():
        """List the configured cells."""
        restapi = context.GLOBAL.admin_api()
        cli.out(cell_formatter(restclient.get(restapi, '/cell/').json()))

    @cell_grp.command()
    @click.argument('name')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(name):
        """Display the details of a cell."""
        restapi = context.GLOBAL.admin_api()
        cli.out(cell_formatter(restclient.get(restapi,
                                              '/cell/%s' % name).json()))

    del _list
    del configure

    return cell_grp
