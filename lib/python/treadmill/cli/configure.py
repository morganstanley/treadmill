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
from treadmill import context
from treadmill import restclient
from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)

_FORMATTER = cli.make_formatter('app')

_APP_REST_PATH = '/app/'

_LIST_TIMEOUT = 20


def _configure(apis, manifest, appname):
    """Configure a Treadmill app"""
    try:
        existing = restclient.get(apis, _APP_REST_PATH + appname).json()
    except restclient.NotFoundError:
        if not manifest:
            raise
        else:
            existing = None

    if manifest:
        app = yaml.load(stream=manifest)

        if existing:
            response = restclient.put(
                apis, _APP_REST_PATH + appname, payload=app
            )
        else:
            response = restclient.post(
                apis, _APP_REST_PATH + appname, payload=app
            )
        existing = response.json()

    cli.out(_FORMATTER(existing))


def _delete(apis, appname):
    """Deletes the app by name."""
    restclient.delete(apis, _APP_REST_PATH + appname)


def _list(apis, match):
    """List configured apps."""
    url = _APP_REST_PATH

    query = {'match': match}
    url += '?' + urllib_parse.urlencode(query)

    response = restclient.get(apis, url, timeout=_LIST_TIMEOUT)
    cli.out(_FORMATTER(response.json()))


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.option('-m', '--manifest', help='App manifest file (stream)',
                  type=click.File('rb'))
    @click.option('--match', help='Application name pattern match')
    @click.option('--delete', help='Delete the app.',
                  is_flag=True, default=False)
    @click.argument('appname', required=False)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(match, manifest, delete, appname):
        """Configure a Treadmill app"""
        restapi = context.GLOBAL.admin_api()
        if appname:
            if delete:
                return _delete(restapi, appname)
            return _configure(restapi, manifest, appname)
        else:
            if not match:
                cli.bad_exit('You must supply a --match option')
            return _list(restapi, match)

    return configure
