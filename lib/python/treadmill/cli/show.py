"""Manage Treadmill app manifest."""
from __future__ import absolute_import

import logging
import urllib

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
        url += '?' + urllib.urlencode([('match', match)])

    response = restclient.get(apis, url)
    cli.out(_STATE_FORMATTER(response.json()))


def _show_list(apis, match, states):
    """Show list of instnces in given state."""
    url = '/state/'
    if match:
        url += '?' + urllib.urlencode([('match', match)])

    response = restclient.get(apis, url)
    names = [item['name']
             for item in response.json() if item['state'] in states]
    for name in names:
        print name


def _show_endpoints(apis, pattern, endpoint):
    """Show cell endpoints."""
    url = '/endpoint/%s' % urllib.quote(pattern)
    if endpoint:
        url += '/' + endpoint

    response = restclient.get(apis, url)
    cli.out(_ENDPOINT_FORMATTER(response.json()))


def _show_instance(apis, instance_id):
    """Show instance manifest."""
    url = '/instance/%s' % urllib.quote(instance_id)

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
    def endpoints(pattern, endpoint):
        """Show application endpoints."""
        apis = context.GLOBAL.state_api(ctx['api'])
        return _show_endpoints(apis, pattern, endpoint)

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
