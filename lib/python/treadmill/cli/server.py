"""Treadmill server CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient


def init():
    """Return top level command handler."""

    server_formatter = cli.make_formatter('server')

    @click.group(name='server')
    @click.option(
        '--api-service-principal', required=False,
        envvar='TREADMILL_API_SERVICE_PRINCIPAL',
        callback=cli.handle_context_opt,
        help='API service principal for SPNEGO auth (default HTTP)',
        expose_value=False
    )
    def server_grp():
        """List & display Treadmill servers.
        """

    @server_grp.command(name='list')
    @click.option(
        '--cell', required=True,
        envvar='TREADMILL_CELL',
        help='Filter servers by cell'
    )
    @click.option(
        '--partition', required=False,
        help='Filter servers by partition'
    )
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list(cell, partition):
        """List all servers."""
        query = {'cell': cell}
        if partition is not None:
            query['partition'] = partition
        url = '/server/?{}'.format(urllib_parse.urlencode(query))
        restapi = context.GLOBAL.admin_api()
        cli.out(server_formatter(restclient.get(restapi, url).json()))

    @server_grp.command()
    @click.argument('name')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(name):
        """Display details of the server."""
        restapi = context.GLOBAL.admin_api()
        cli.out(
            server_formatter(
                restclient.get(restapi, '/server/{}'.format(name)).json()
            )
        )

    del _list
    del configure

    return server_grp
