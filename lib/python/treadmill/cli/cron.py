"""Treadmill cron CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)

_ON_EXCEPTIONS = cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
_FORMATTER = cli.make_formatter('cron')

_REST_PATH = '/cron/'


def init():
    """Return top level command handler."""
    # pylint: disable=too-many-statements

    @click.group()
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def cron_group():
        """Manage Treadmill cron jobs"""

    @cron_group.command()
    @click.argument('job_id')
    @click.argument('event', required=False)
    @click.option('--resource',
                  help='The resource to schedule, e.g. an app name')
    @click.option('--expression', help='The cron expression for scheduling')
    @click.option('--count', help='The number of instances to start',
                  type=int)
    @_ON_EXCEPTIONS
    def configure(job_id, event, resource, expression, count):
        """Create or modify an existing app start schedule"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + job_id

        data = {}

        if event:
            data['event'] = event
        if resource:
            data['resource'] = resource
        if expression:
            data['expression'] = expression
        if count is not None:
            data['count'] = count

        if data:
            try:
                _LOGGER.debug('Creating cron job: %s', job_id)
                restclient.post(restapi, url, payload=data)
            except restclient.AlreadyExistsError:
                _LOGGER.debug('Updating cron job: %s', job_id)
                restclient.put(restapi, url, payload=data)

        _LOGGER.debug('Retrieving cron job: %s', job_id)
        job = restclient.get(restapi, url).json()
        _LOGGER.debug('job: %r', job)

        cli.out(_FORMATTER(job))

    @cron_group.command(name='list')
    @click.option('--match', help='Cron name pattern match')
    @click.option('--resource', help='Pattern match on the resource name')
    @_ON_EXCEPTIONS
    def _list(match, resource):
        """List out all cron events"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH
        query = {}
        if match:
            query['match'] = match
        if resource:
            query['resource'] = resource

        if query:
            qstr = urllib_parse.urlencode(query)
            url = '{}?{}'.format(url, qstr)

        response = restclient.get(restapi, url)
        jobs = response.json()
        _LOGGER.debug('jobs: %r', jobs)

        cli.out(_FORMATTER(jobs))

    @cron_group.command()
    @click.argument('job_id')
    @_ON_EXCEPTIONS
    def delete(job_id):
        """Delete a cron events"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + job_id
        restclient.delete(restapi, url)

    @cron_group.command()
    @click.argument('job_id')
    @_ON_EXCEPTIONS
    def pause(job_id):
        """Pause a cron job"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + job_id + '?pause=true'
        job = restclient.put(restapi, url, {}).json()
        _LOGGER.debug('job: %r', job)

        cli.out(_FORMATTER(job))

    @cron_group.command()
    @click.argument('job_id')
    @_ON_EXCEPTIONS
    def resume(job_id):
        """Resume a cron job"""
        restapi = context.GLOBAL.cell_api()
        url = _REST_PATH + job_id + '?resume=true'
        job = restclient.put(restapi, url, {}).json()
        _LOGGER.debug('job: %r', job)

        cli.out(_FORMATTER(job))

    del configure
    del _list
    del delete
    del pause
    del resume

    return cron_group
