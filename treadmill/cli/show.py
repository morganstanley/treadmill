"""Manage Treadmill app manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import urllib.request
import urllib.parse
import urllib.error

import click

from treadmill import cli
from treadmill import restclient
from treadmill import context


_LOGGER = logging.getLogger(__name__)

_STATE_FORMATTER = cli.make_formatter('instance-state')

_ENDPOINT_FORMATTER = cli.make_formatter('endpoint')

_APP_FORMATTER = cli.make_formatter('app')


def _show_state(apis, match, finished):
    """Show cell state."""
    url = '/state/'
    query = []
    if match:
        query.append(('match', match))
    if finished:
        query.append(('finished', '1'))

    if query:
        url += '?' + '&'.join(
            [urllib.parse.urlencode([param]) for param in query]
        )

    response = restclient.get(apis, url)
    cli.out(_STATE_FORMATTER(response.json()))


def _show_list(apis, match, states, finished=False, partition=None):
    """Show list of instnces in given state."""
    url = '/state/'
    query = []
    if match:
        query.append(('match', match))
    if finished:
        query.append(('finished', '1'))
    if partition is not None:
        query.append(('partition', partition))

    if query:
        url += '?' + '&'.join(
            [urllib.parse.urlencode([param]) for param in query]
        )

    response = restclient.get(apis, url)
    names = [item['name']
             for item in response.json() if item['state'] in states]
    for name in names:
        cli.out(name)


def _show_endpoints(apis, pattern, endpoint, proto):
    """Show cell endpoints."""
    url = '/endpoint/%s' % urllib.parse.quote(pattern)
    if endpoint:
        if proto:
            url += '/' + proto
        else:
            url += '/*'

        url += '/' + endpoint

    response = restclient.get(apis, url)
    endpoints = [{
        'name': end['name'],
        'proto': end['proto'],
        'endpoint': end['endpoint'],
        'hostport': '{0}:{1}'.format(end['host'], end['port'])
    } for end in response.json()]

    cli.out(_ENDPOINT_FORMATTER(endpoints))


def _show_instance(apis, instance_id):
    """Show instance manifest."""
    url = '/instance/%s' % urllib.parse.quote(instance_id)

    response = restclient.get(apis, url)
    cli.out(_APP_FORMATTER(response.json()))


def init():
    """Return top level command handler."""

    ctx = {}

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_STATEAPI')
    def show(api):
        """Show state of scheduled applications."""
        ctx['api'] = api

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--finished', is_flag=True, default=False,
                  help='Show finished instances.')
    def state(match, finished):
        """Show state of Treadmill scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_state(apis, match, finished)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def pending(match, partition):
        """Show pending instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['pending'], partition=partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def running(match, partition):
        """Show running instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['running'], partition=partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def finished(match, partition):
        """Show finished instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(
            apis, match, ['finished'], finished=True, partition=partition
        )

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def scheduled(match, partition):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(
            apis, match, ['running', 'scheduled'], partition=partition
        )

    @show.command(name='all')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def _all(match, partition):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(
            apis,
            match,
            ['pending', 'running', 'scheduled'],
            partition=partition
        )

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('pattern')
    @click.argument('endpoint', required=False)
    @click.argument('proto', required=False)
    def endpoints(pattern, endpoint, proto):
        """Show application endpoints."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_endpoints(apis, pattern, endpoint, proto)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('instance_id')
    def instance(instance_id):
        """Show scheduled instance manifest."""
        apis = context.GLOBAL.cell_api(ctx['api'])
        return _show_instance(apis, instance_id)

    del _all
    del running
    del scheduled
    del pending
    del finished
    del instance
    del state
    del endpoints
    return show
