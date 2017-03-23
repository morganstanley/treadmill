"""Download treadmill app metrics given a pattern.

The files are downloaded for current directory, or it can be overwritten with
--outdir command line option.

"""


import sys

import logging
import os
import urllib.request
import urllib.parse
import urllib.error

import click

from .. import discovery
from .. import cli
from .. import fs
from .. import rrdutils
from .. import context
from .. import admin


_LOGGER = logging.getLogger(__name__)

# TODO: this list should be discoverable from the server rather than
#                hardcoded. GET /metrics/core should return this list.
_SYSTEM_SERVICES = [
    # Total metrics for non-treadmill (system), core services and all apps.
    'treadmill.system',
    'treadmill.core',
    'treadmill.apps',
]


def _get_nodeinfo_url(cell):
    """Get nodeinfo app url using discovery."""
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    cell_obj = admin_cell.get(cell)

    nodeinfo_app = '%s.%s' % (cell_obj['username'], 'nodeinfo')
    nodeinfo_iter = discovery.iterator(
        context.GLOBAL.zk.conn,
        nodeinfo_app,
        'http',
        watch=False
    )

    for (_app, hostport) in nodeinfo_iter:
        return 'http://%s' % hostport

    _LOGGER.critical('%s: %s is not running.', cell, nodeinfo_app)
    sys.exit(-1)


def _get_app_metrics(nodeinfo_url, outdir, appendpoint, hostport):
    """Retreives app metrics given discovery info."""
    fs.mkdir_safe(outdir)

    host, _port = hostport.split(':')
    instance, _proto, _endpoint = appendpoint.split(':')
    metrics_url = '%s/%s/metrics/apps/%s' % (
        nodeinfo_url, host, urllib.parse.quote(instance))

    rrdfile = os.path.join(outdir, '%s.rrd' % instance)
    _download_rrd(metrics_url, rrdfile)


def _get_server_metrics(nodeinfo_url, outdir, server, services):
    """Get core services metrics."""
    _LOGGER.info('Processing %s.', server)
    fs.mkdir_safe(outdir)

    for svc in services:
        metrics_url = '%s/%s/metrics/core/%s' % (nodeinfo_url,
                                                 server,
                                                 urllib.parse.quote(svc))
        rrdfile = os.path.join(outdir, '%s-%s.rrd' % (server, svc))
        _download_rrd(metrics_url, rrdfile)


def _download_rrd(metrics_url, rrdfile):
    """Get rrd file and store in output directory."""
    _LOGGER.info('%s', metrics_url)
    request = urllib.request.Request(metrics_url)
    try:
        with open(rrdfile, 'w+') as f:
            f.write(urllib.request.urlopen(request).read())

        rrdutils.gen_graph(rrdfile, rrdutils.RRDTOOL,
                           show_mem_limit=False)
    except urllib.error.HTTPError as err:
        _LOGGER.warning('%s: %s, %s', metrics_url, err.code, err.reason)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--outdir', '-o', help='Output directory.',
                  type=click.Path(exists=True),
                  required=True)
    @click.option('--servers', type=cli.LIST,
                  help='List of servers to get core metrics')
    @click.option('--services', type=cli.LIST,
                  help='Subset of core services.')
    @click.argument('app', required=False)
    def metrics(outdir, servers, services, app):
        """Retrieve node / app metrics."""
        cell = context.GLOBAL.cell
        nodeinfo_url = _get_nodeinfo_url(cell)
        if not services:
            services = _SYSTEM_SERVICES

        if app:
            pattern = app.replace('%', '*')
            discovery_iter = discovery.iterator(
                context.GLOBAL.zk.conn,
                pattern,
                'ssh',
                watch=False
            )

            for (appendpoint, hostport) in discovery_iter:
                _get_app_metrics(nodeinfo_url, outdir, appendpoint, hostport)

        for server in servers:
            _get_server_metrics(nodeinfo_url, outdir, server, services)

    return metrics
