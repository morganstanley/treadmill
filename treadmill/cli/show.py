"""Manage Treadmill app manifest."""


import logging
import urllib.request
import urllib.parse
import urllib.error

import click

from .. import cli
from treadmill import restclient
from treadmill import context


_LOGGER = logging.getLogger(__name__)

_STATE_FORMATTER = cli.make_formatter(cli.InstanceStatePrettyFormatter)

_ENDPOINT_FORMATTER = cli.make_formatter(cli.EndpointPrettyFormatter)

_APP_FORMATTER = cli.make_formatter(cli.AppPrettyFormatter)


def _show_state(apis, match):
    """Show cell state."""
    url = '/state/'
    if match:
        url += '?' + urllib.parse.urlencode([('match', match)])

    response = restclient.get(apis, url)
    cli.out(_STATE_FORMATTER(response.json()))


def _show_list(apis, match, states):
    """Show list of instnces in given state."""
    url = '/state/'
    if match:
        url += '?' + urllib.parse.urlencode([('match', match)])

    response = restclient.get(apis, url)
    names = [item['name']
             for item in response.json() if item['state'] in states]
    for name in names:
        print(name)


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
    @cli.ON_REST_EXCEPTIONS
    @click.option('--match', help='Application name pattern match')
    def state(match):
        """Show state of Treadmill scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_state(apis, match)

    @show.command()
    @cli.ON_REST_EXCEPTIONS
    @click.option('--match', help='Application name pattern match')
    def pending(match):
        """Show pending instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['pending'])

    @show.command()
    @cli.ON_REST_EXCEPTIONS
    @click.option('--match', help='Application name pattern match')
    def running(match):
        """Show running instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['running'])

    @show.command()
    @cli.ON_REST_EXCEPTIONS
    @click.option('--match', help='Application name pattern match')
    def scheduled(match):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['running', 'scheduled'])

    @show.command(name='all')
    @cli.ON_REST_EXCEPTIONS
    @click.option('--match', help='Application name pattern match')
    def _all(match):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_list(apis, match, ['pending', 'running', 'scheduled'])

    @show.command()
    @cli.ON_REST_EXCEPTIONS
    @click.argument('pattern')
    @click.argument('endpoint', required=False)
    @click.argument('proto', required=False)
    def endpoints(pattern, endpoint, proto):
        """Show application endpoints."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_endpoints(apis, pattern, endpoint, proto)

    @show.command()
    @cli.ON_REST_EXCEPTIONS
    @click.argument('instance_id')
    def instance(instance_id):
        """Show scheduled instance manifest."""
        apis = context.GLOBAL.cell_api(ctx['api'])
        return _show_instance(apis, instance_id)

    del _all
    del running
    del scheduled
    del pending
    del instance
    del state
    del endpoints
    return show
