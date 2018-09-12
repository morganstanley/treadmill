"""Show Treadmill instance logs.
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
from treadmill import websocketutils as wsu
from treadmill import restclient
from treadmill.websocket import client as wsclient

_LOGGER = logging.getLogger(__name__)


def _find_endpoints(pattern, proto, endpoint):
    """Return all the matching endpoints in the cell.

    The return value is a dict with host-endpoint assigments as key-value
    pairs.
    """
    apis = context.GLOBAL.state_api()

    url = '/endpoint/{}/{}/{}'.format(pattern, proto, endpoint)

    endpoints = restclient.get(apis, url).json()
    if not endpoints:
        cli.bad_exit('Nodeinfo API couldn\'t be found')

    return endpoints


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--all', 'all_logs', is_flag=True, default=False,
                  help='Download all logs (not just the latest) as a file.')
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    @click.argument('app-or-svc')
    @click.option('--cell',
                  callback=cli.handle_context_opt,
                  envvar='TREADMILL_CELL',
                  expose_value=False,
                  required=True)
    @click.option('--host',
                  help='Hostname where to look for the logs',
                  required=False)
    @click.option('--service',
                  help='The name of the service for which the logs are '
                       'to be retreived',
                  required=False)
    @click.option('--uniq',
                  default='running',
                  help='The container id. Specify this if you look for a '
                       'not-running (terminated) application\'s log',
                  required=False)
    @cli.handle_exceptions(
        restclient.CLI_REST_EXCEPTIONS + wsclient.CLI_WS_EXCEPTIONS)
    def logs(all_logs, app_or_svc, host, service, uniq):
        """View or download application's service logs.

        Arguments are expected to be specified a) either as one string or b)
        parts defined one-by-one ie.:

        a) <appname>/<uniq or running>/service/<servicename>

        b) <appname> --uniq <uniq> --service <servicename>

        Eg.:

        a) proid.foo#1234/xz9474as8/service/my-echo

        b) proid.foo#1234 --uniq xz9474as8 --service my-echo

        For the latest log simply omit 'uniq':

        proid.foo#1234 --service my-echo
        """
        try:
            app, uniq, logtype, logname = app_or_svc.split('/', 3)
        except ValueError:
            app, uniq, logtype, logname = app_or_svc, uniq, 'service', service

        if logname is None:
            cli.bad_exit('Please specify the "service" parameter.')

        ws_api = context.GLOBAL.ws_api()

        if host is None:
            instance = None
            if uniq == 'running':
                instance = wsu.find_running_instance(app, ws_api)

            if not instance:
                instance = wsu.find_uniq_instance(app, uniq, ws_api)

            if not instance:
                cli.bad_exit('No {}instance could be found.'.format(
                    'running ' if uniq == 'running' else ''))

            _LOGGER.debug('Found instance: %s', instance)

            host = instance['host']
            uniq = instance['uniq']

        try:
            (endpoint,) = [
                ep
                for ep in _find_endpoints(
                    urllib_parse.quote('root.*'),
                    'tcp',
                    'nodeinfo',
                )
                if ep['host'] == host
            ]
        except ValueError as err:
            _LOGGER.exception(err)
            cli.bad_exit('No endpoint found on %s', host)

        api = 'http://{0}:{1}'.format(endpoint['host'], endpoint['port'])
        logurl = '/local-app/{}/{}/{}/{}'.format(
            urllib_parse.quote(app),
            urllib_parse.quote(uniq),
            logtype,
            urllib_parse.quote(logname)
        )

        if all_logs:
            logurl += '?all=1'

        resp = restclient.get(api, logurl)

        click.echo(resp.text)

    return logs
