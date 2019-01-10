"""Manage Treadmill app manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import restclient
from treadmill import context
from treadmill import utils


_LOGGER = logging.getLogger(__name__)

_FINISHED_STATES = ['finished', 'aborted', 'killed', 'terminated']

_STATE_FORMATTER = cli.make_formatter('instance-state')

_FINISHED_STATE_FORMATTER = cli.make_formatter('instance-finished-state')

_ENDPOINT_FORMATTER = cli.make_formatter('endpoint')

_APP_FORMATTER = cli.make_formatter('app')


def _get_state(apis, match=None, finished=False, partition=None):
    """Get cell state."""
    url = '/state/'

    query = {}
    if match:
        query['match'] = match
    if finished:
        query['finished'] = 'true'
    if partition:
        query['partition'] = partition

    if query:
        url += '?' + urllib_parse.urlencode(query)

    response = restclient.get(apis, url)
    return response.json()


def _show_state(apis, match=None, finished=False, partition=None):
    """Show cell state."""
    state = _get_state(apis, match, finished, partition)
    cli.out(_STATE_FORMATTER(state))


def _show_finished(apis, match=None, partition=None):
    state = _get_state(apis, match=match, finished=True, partition=partition)

    result = []
    for item in state:
        if item['state'] not in _FINISHED_STATES:
            continue

        details = None
        if item.get('exitcode') is not None:
            details = 'return code: {}'.format(item['exitcode'])
        if item.get('signal') is not None:
            details = 'signal: {}'.format(utils.signal2name(item['signal']))
        if item.get('aborted_reason'):
            details = 'reason: {}'.format(item['aborted_reason'])
        if item.get('terminated_reason'):
            details = 'reason: {}'.format(item['terminated_reason'])
        if item.get('oom'):
            details = 'out of memory'

        result.append({
            'name': item['name'],
            'state': item['state'],
            'host': item['host'],
            'when': utils.strftime_utc(item['when']),
            'details': details,
        })

    cli.out(_FINISHED_STATE_FORMATTER(result))


def _show_list(apis, match, states, finished=False, partition=None):
    """Show list of instnces in given state."""
    state = _get_state(apis, match, finished, partition)
    names = [item['name'] for item in state if item['state'] in states]
    for name in names:
        cli.out(name)


def _show_endpoints(apis, pattern, endpoint, proto):
    """Show cell endpoints."""
    url = '/endpoint/%s' % urllib_parse.quote(pattern)
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
        'hostport': '{0}:{1}'.format(end['host'], end['port']),
        'state': end.get('state')
    } for end in response.json()]

    cli.out(_ENDPOINT_FORMATTER(endpoints))


def _show_instance(apis, instance_id):
    """Show instance manifest."""
    url = '/instance/%s' % urllib_parse.quote(instance_id)

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
    def show():
        """Show state of scheduled applications.
        """

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--finished', is_flag=True, default=False,
                  help='Show finished instances.')
    @click.option('--partition', help='Filter apps by partition')
    def state(match, finished, partition):
        """Show state of Treadmill scheduled instances."""
        apis = context.GLOBAL.state_api()
        return _show_state(apis, match, finished, partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def pending(match, partition):
        """Show pending instances."""
        apis = context.GLOBAL.state_api()
        return _show_list(apis, match, ['pending'], partition=partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def running(match, partition):
        """Show running instances."""
        apis = context.GLOBAL.state_api()
        return _show_list(apis, match, ['running'], partition=partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def finished(match, partition):
        """Show finished instances."""
        apis = context.GLOBAL.state_api()
        return _show_finished(apis, match, partition)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def scheduled(match, partition):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api()
        return _show_list(
            apis, match, ['running', 'scheduled'], partition=partition
        )

    @show.command(name='all')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Application name pattern match')
    @click.option('--partition', help='Filter apps by partition')
    def _all(match, partition):
        """Show scheduled instances."""
        apis = context.GLOBAL.state_api()
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
        apis = context.GLOBAL.state_api()
        return _show_endpoints(apis, pattern, endpoint, proto)

    @show.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.argument('instance_id')
    def instance(instance_id):
        """Show scheduled instance manifest."""
        apis = context.GLOBAL.cell_api()
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
