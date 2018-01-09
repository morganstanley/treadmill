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
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    @click.option('--all', 'all_instances', required=False, is_flag=True,
                  help='Stop all instances matching the app provided')
    @click.argument('instances', nargs=-1)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def stop(api, all_instances, instances):
        """Stop (unschedule, terminate) Treadmill instance(s)."""
        if not instances:
            return

        apis = context.GLOBAL.cell_api(api)

        if all_instances:
            endpoint = '/instance/?match=' + instances[0]
            instances = restclient.get(apis, endpoint).json()['instances']
            if not instances:
                return

        response = restclient.post(apis, '/instance/_bulk/delete',
                                   payload=dict(instances=list(instances)))

        return response.json()

    return stop
