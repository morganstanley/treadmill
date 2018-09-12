"""Stop Treadmill instances.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--all', 'all_instances', required=False, is_flag=True,
                  help='Stop all instances matching the app provided')
    @click.argument('instances', nargs=-1)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def stop(all_instances, instances):
        """Stop (unschedule, terminate) Treadmill instance(s)."""
        if not instances:
            return None

        apis = context.GLOBAL.cell_api()

        if all_instances:
            endpoint = '/instance/?match=' + instances[0]
            instances = restclient.get(apis, endpoint).json()['instances']
            if not instances:
                return None

        response = restclient.post(apis, '/instance/_bulk/delete',
                                   payload=dict(instances=list(instances)))

        return response.json()

    return stop
