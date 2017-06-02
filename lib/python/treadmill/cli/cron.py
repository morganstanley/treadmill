"""
Treadmill cron CLI.
"""
from __future__ import absolute_import

import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)

_ON_EXCEPTIONS = cli.handle_exceptions(cli.REST_EXCEPTIONS)
_FORMATTER = cli.make_formatter(cli.CronPrettyFormatter)

_REST_PATH = '/cron/'


def init():
    """Return top level command handler."""
    ctx = {}

    @click.group()
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_CELLAPI')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def cron_group(api):
        """Manage Treadmill cron jobs"""
        ctx['api'] = api

    @cron_group.command()
    @click.argument('job_id')
    @click.argument('event',
                    type=click.Choice([
                        'app:start', 'app:stop', 'monitor:set-count'
                    ]))
    @click.option('--resource',
                  help='The resource to schedule, e.g. an app name')
    @click.option('--expression', help='The cron expression for scheduling')
    @click.option('--count', help='The number of instances to start',
                  type=int)
    @_ON_EXCEPTIONS
    def configure(job_id, event, resource, expression, count):
        """Create or modify an existing app start schedule"""
        restapi = context.GLOBAL.cell_api(ctx['api'])
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
    @_ON_EXCEPTIONS
    def _list():
        """List out all cron events"""
        restapi = context.GLOBAL.cell_api(ctx['api'])
        response = restclient.get(restapi, _REST_PATH)
        jobs = response.json()
        _LOGGER.debug('jobs: %r', jobs)

        cli.out(_FORMATTER(jobs))

    @cron_group.command()
    @click.argument('job_id')
    @_ON_EXCEPTIONS
    def delete(job_id):
        """Delete a cron events"""
        restapi = context.GLOBAL.cell_api(ctx['api'])
        url = _REST_PATH + job_id
        restclient.delete(restapi, url)

    del configure
    del _list
    del delete

    return cron_group
