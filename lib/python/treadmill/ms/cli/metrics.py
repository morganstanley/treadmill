"""Download treadmill application or system metrics.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click
from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import websocketutils as wsu
from treadmill import restclient
from treadmill import rrdutils
from treadmill import utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import rrdmetrics


_LOGGER = logging.getLogger(__name__)


def _find_endpoints(pattern, proto, endpoint, api=None):
    """Return all the matching endpoints in the cell.

    The return value is a dict with host-endpoint assigments as key-value
    pairs.
    """
    apis = context.GLOBAL.state_api(api)

    url = '/endpoint/{}/{}/{}'.format(pattern, proto, endpoint)

    endpoints = restclient.get(apis, url).json()
    if not endpoints:
        cli.bad_exit('Nodeinfo API couldn\'t be found')

    return endpoints


def _gen_outdir_name(*args):
    """Generate the (nfsweb friendly) name of the output directory."""
    # remove the '.rrd' extension if there's any and replace '#' with '-'
    return '-'.join(
        [arg.rsplit('.rrd', 1)[0].replace('#', '-') for arg in args])


# Disable warning about redefined-builtin 'long' in the options
# pylint: disable=W0622
def init():
    """Top level command handler."""

    ctx = {}

    @click.group()
    @click.option('--api',
                  envvar='TREADMILL_STATEAPI',
                  help='State API url to use.',
                  required=False)
    @click.option('--cell',
                  callback=cli.handle_context_opt,
                  envvar='TREADMILL_CELL',
                  expose_value=False,
                  required=True)
    @click.option('--outdir',
                  '-o',
                  help='Output directory.',
                  required=False,
                  type=click.Path(exists=False))
    @click.option('--ws-api', help='Websocket API url to use.', required=False)
    def metrics(api, outdir, ws_api):
        """Retrieve node / app metrics and visualize the data."""
        ctx['state_api'] = api
        ctx['outdir'] = outdir
        ctx['ws_api'] = ws_api

    @metrics.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('app')
    @click.option('--host',
                  help='Hostname where to look for the metrics',
                  required=False)
    @click.option('--long', is_flag=True, default=False,
                  help='Metrics for longer timeframe.')
    @click.option('--uniq',
                  default='running',
                  help='The container id. Specify this if you look for a '
                       'not-running (terminated) application\'s log',
                  required=False)
    def app(app, host, long, uniq):
        """Get the metrics of the application in params.

        App is expected to be specified a) either as one string or b)
        parts defined one-by-one ie.:

        a) <appname>/<uniq or running>

        b) <appname> --uniq <uniq>

        Eg.:

        a) proid.foo#1234/xz9474as8
           proid.foo#1234/running

        b) proid.foo#1234 --uniq xz9474as8
           proid.foo#1234 --uniq running

        For the latest metrics simply omit 'uniq':

        proid.foo#1234
        """

        if not utils.which(rrdutils.RRDTOOL):
            cli.bad_exit('The rrdtool utility cannot be found in the PATH')
        timeframe = 'long' if long else 'short'

        if '/' in app:
            app, uniq = app.split('/', 2)

        _LOGGER.debug('Find out where instance is/was running.')

        if host is None:
            instance = None
            if uniq == 'running':
                instance = wsu.find_running_instance(app, ctx['ws_api'])

            if not instance:
                instance = wsu.find_uniq_instance(app, uniq, ctx['ws_api'])

            if not instance:
                cli.bad_exit('No {}instance could be found.'.format(
                    'running ' if uniq == 'running' else ''))

            host = instance['host']
            uniq = instance['uniq']

            _LOGGER.info('%s/%s is/was running on %s', app, uniq, host)

        try:
            endpoint, = [ep
                         for ep in _find_endpoints(
                             urllib_parse.quote('root.*'), 'tcp',
                             'nodeinfo', ctx['state_api'])
                         if ep['host'] == host]
        except ValueError as err:
            _LOGGER.exception(err)
            cli.bad_exit('No endpoint found on %s', host)

        outdir = ctx['outdir'] if ctx['outdir'] else _gen_outdir_name(app,
                                                                      uniq)
        report_file = rrdmetrics.get_app_metrics(
            endpoint, app, timeframe, uniq, outdir=outdir
        )
        cli.echo_green('Please open %s to see the metrics.', report_file)

    @metrics.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('servers', nargs=-1)
    @click.option('--services', type=cli.LIST, help='Subset of core services.')
    @click.option('--long', is_flag=True, default=False,
                  help='Metrics for longer timeframe.')
    def sys(servers, services, long):
        """Get the metrics of the server(s) in params."""

        if not utils.which(rrdutils.RRDTOOL):
            cli.bad_exit('The rrdtool utility cannot be found in the PATH')
        timeframe = 'long' if long else 'short'

        endpoints = _find_endpoints(urllib_parse.quote('root.*'), 'tcp',
                                    'nodeinfo', ctx['state_api'])

        for server in servers:
            try:
                endpoint, = [ep for ep in endpoints if ep['host'] == server]
            except ValueError as err:
                _LOGGER.exception(err)
                cli.bad_exit('No endpoint found on %s', server)

            outdir = ctx['outdir'] if ctx['outdir'] else server
            for report_file in rrdmetrics.get_server_metrics(
                    endpoint, server, timeframe, services, outdir):

                cli.echo_green(
                    'Please open %s to see the %s metrics.',
                    report_file, server
                )

    @metrics.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('rrd_file', type=click.Path(exists=True, readable=True))
    @click.option('--long', is_flag=True, default=False,
                  help='Metrics for longer timeframe.')
    def from_file(rrd_file, long):
        """Use the metrics from the specified file."""
        timeframe = 'long' if long else 'short'

        if not utils.which(rrdutils.RRDTOOL):
            cli.bad_exit('The rrdtool utility cannot be found in the PATH')

        outdir = ctx['outdir'] if ctx['outdir'] else _gen_outdir_name(
            os.path.basename(rrd_file))
        report_file = rrdmetrics.gen_report(rrd_file, timeframe, outdir)
        cli.echo_green('Please open %s to see the metrics.', report_file)

    del app
    del sys
    del from_file

    return metrics
