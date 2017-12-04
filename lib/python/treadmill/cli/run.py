"""Manage Treadmill app manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import shlex

import click
import six

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MEM = '100M'
_DEFAULT_DISK = '100M'
_DEFAULT_CPU = '10%'


def _run(apis,
         count,
         manifest,
         memory,
         cpu,
         disk,
         tickets,
         service,
         restart_limit,
         restart_interval,
         endpoint,
         appname,
         command):
    """Run Treadmill app."""
    # too many branches
    #
    # pylint: disable=R0912
    app = {}
    if manifest:
        with io.open(manifest, 'rb') as fd:
            app = yaml.load(stream=fd)

    if endpoint:
        app['endpoints'] = [{'name': name, 'port': port}
                            for name, port in endpoint]
    if tickets:
        app['tickets'] = tickets

    if command:
        if not service:
            # Take the basename of the command, always assume / on all
            # platforms.
            service = os.path.basename(shlex.split(command[0])[0])

    services_dict = {svc['name']: svc for svc in app.get('services', [])}
    if service:
        if service not in services_dict:
            services_dict[service] = {
                'name': service,
                'restart': {
                    'limit': restart_limit,
                    'interval': restart_interval,
                }
            }

        if command:
            services_dict[service]['command'] = ' '.join(list(command))

    if services_dict:
        app['services'] = list(six.itervalues(services_dict))

    if app:
        # Ensure defaults are set.
        if 'memory' not in app:
            app['memory'] = _DEFAULT_MEM
        if 'disk' not in app:
            app['disk'] = _DEFAULT_DISK
        if 'cpu' not in app:
            app['cpu'] = _DEFAULT_CPU

        # Override if requested.
        if memory is not None:
            app['memory'] = str(memory)
        if disk is not None:
            app['disk'] = str(disk)
        if cpu is not None:
            app['cpu'] = str(cpu)

    url = '/instance/' + appname
    if count:
        url += '?count=%d' % count

    response = restclient.post(apis, url, payload=app)
    for instance_id in response.json()['instances']:
        cli.out(instance_id)


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
    @click.option('--count', help='Number of instances to start',
                  default=1)
    @click.option('-m', '--manifest', help='App manifest file (stream)',
                  type=click.Path(exists=True, readable=True))
    @click.option('--memory', help='Memory demand, default %s.' % _DEFAULT_MEM,
                  metavar='G|M',
                  callback=cli.validate_memory)
    @click.option('--cpu', help='CPU demand, default %s.' % _DEFAULT_CPU,
                  metavar='XX%',
                  callback=cli.validate_cpu)
    @click.option('--disk', help='Disk demand, default %s.' % _DEFAULT_DISK,
                  metavar='G|M',
                  callback=cli.validate_disk)
    @click.option('--tickets', help='Tickets.',
                  type=cli.LIST)
    @click.option('--service', help='Service name.', type=str)
    @click.option('--restart-limit', type=int, default=0,
                  help='Service restart limit.')
    @click.option('--restart-interval', type=int, default=60,
                  help='Service restart limit interval.')
    @click.option('--endpoint', help='Network endpoint.',
                  type=(str, int), multiple=True)
    @click.argument('appname')
    @click.argument('command', nargs=-1)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def run(api,
            count,
            manifest,
            memory,
            cpu,
            disk,
            tickets,
            service,
            restart_limit,
            restart_interval,
            endpoint,
            appname,
            command):
        """Schedule Treadmill app.

        With no options, will schedule already configured app, fail if app
        is not configured.

        When manifest (or other options) are specified, they will be merged
        on top of existing manifest if it exists.
        """
        apis = context.GLOBAL.cell_api(api)
        return _run(
            apis, count, manifest, memory, cpu, disk, tickets,
            service, restart_limit, restart_interval, endpoint,
            appname, command)

    return run
