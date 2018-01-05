"""Implementation of treadmill admin logs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill import zknamespace as z
from treadmill import rrdutils
from treadmill import utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import rrdmetrics


def _nodeinfo_endpoint(host):
    """Find nodeinfo endpoint on host"""
    zkclient = context.GLOBAL.zk.conn
    nodeinfo_zk_path = '{}/{}'.format(z.ENDPOINTS, 'root')
    for node in zkclient.get_children(nodeinfo_zk_path):
        if 'nodeinfo' in node and host in node:
            data, _metadata = zkclient.get(
                '{}/{}'.format(nodeinfo_zk_path, node)
            )
            return data.split(':')


def _gen_outdir_name(*args):
    """Generate the (nfsweb friendly) name of the output directory."""
    # remove the '.rrd' extension if there's any and replace '#' with '-'
    return '-'.join(
        [arg.rsplit('.rrd', 1)[0].replace('#', '-') for arg in args])


# Disable warning about redefined-builtin 'long' in the options
# pylint: disable=W0622
def init():
    """Return top level command handler."""
    ctx = {}

    @click.group()
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
    def metrics(outdir):
        """View application's service logs."""
        ctx['outdir'] = outdir

    @metrics.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.argument('app')
    @click.option('--long', is_flag=True, default=False,
                  help='Metrics for longer timeframe.')
    @click.option('--uniq',
                  help='The container id. Specify this if you look for a '
                       'not-running (terminated) application\'s log',
                  required=True)
    @click.option('--host',
                  help='Hostname where to look for the metrics',
                  required=True)
    def app(app, long, uniq, host):
        """Get metrics of appliations
        """
        if not utils.which(rrdutils.RRDTOOL):
            cli.bad_exit('The rrdtool utility cannot be found in the PATH')
        timeframe = 'long' if long else 'short'

        host, port = _nodeinfo_endpoint(host)
        endpoint = {'host': host, 'port': port}
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

        for server in servers:
            host, port = _nodeinfo_endpoint(server)
            endpoint = {'host': host, 'port': port}
            outdir = ctx['outdir'] if ctx['outdir'] else server
            for report_file in rrdmetrics.get_server_metrics(
                    endpoint, server, timeframe, services, outdir):
                cli.echo_green(
                    'Please open %s to see the metrics.', report_file
                )

    del app
    del sys

    return metrics
